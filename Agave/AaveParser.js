const Web3 = require('web3')
const fs = require('fs');
const { toBN, toWei, fromWei } = Web3.utils
const Addresses = require("./Addresses.js");
const {normalize} = require('../utils/TokenHelper.js')

const BN_1e18 = toBN(10).pow(toBN(18));

const sleep = async seconds => {
    return new Promise(resolve => setTimeout(resolve, seconds * 1000))
  }

/**
 * a small retry wrapper with an incrameting 5s sleep delay
 * @param {*} fn 
 * @param {*} params 
 * @param {*} retries 
 * @returns 
 */
async function retry(fn, params, retries = 0) {
    try {
        const res = await  fn(...params)
        if(retries){
            console.log(`retry success after ${retries} retries`)
        } else {
            console.log(`success on first try`)
        }
        return res
    } catch (e) {
        console.error(e)
        retries++
        console.log(`retry #${retries}`)
        await new Promise(resolve => setTimeout(resolve, 1000 * 5 * retries))
        return retry(fn, params, retries)
    }
}

class Aave {
    constructor(aaveInfo, network, web3, fileName, heavyUpdateInterval = 24) {
      this.web3 = web3
      this.network = network
      this.fileName = fileName
      this.lendingPoolAddressesProvider = new web3.eth.Contract(Addresses.lendingPoolAddressesProviderAbi, aaveInfo[network].lendingPoolAddressesProviderAddress)
      this.aaveUserInfo = new web3.eth.Contract(Addresses.aaveUserInfoAbi, Addresses.aaveUserInfoAddress[network])

      this.multicall = new web3.eth.Contract(Addresses.multicallAbi, Addresses.multicallAddress[network])
      this.deployBlock = aaveInfo[network].deployBlock
      this.blockStepInInit = aaveInfo[network].blockStepInInit
      this.multicallSize = aaveInfo[network].multicallSize

      this.users = {}
      this.userList = []

      this.lastUpdateBlock = 0

      this.mainCntr = 0
      this.heavyUpdateInterval = heavyUpdateInterval

      this.output = {}


      this.markets = []
      this.names = {}
      this.decimals = {}
      this.lastUpdateTime = 0

      this.liquidationIncentive = {}
      this.collateralFactors = {}
      this.prices = {}
      this.oraclePrices = {}
      this.underlying = {}
      this.closeFactor = {}
      this.borrowCaps = {}
      this.collateralCaps = {}

      this.totalCollateral = {}
      this.totalBorrows = {}   
    }

    getData() {
        const result =
        {
            "markets" : JSON.stringify(this.markets),
            "prices" : JSON.stringify(this.prices),
            "lastUpdateTime" : this.lastUpdateTime,
            "liquidationIncentive" : JSON.stringify(this.liquidationIncentive),
            "collateralFactors" : JSON.stringify(this.collateralFactors),
            "names" : JSON.stringify(this.names),
            "borrowCaps" : JSON.stringify(this.borrowCaps),
            "collateralCaps" : JSON.stringify(this.collateralCaps),
            "decimals" : JSON.stringify(this.decimals),
            "underlying" : JSON.stringify(this.underlying),
            "closeFactor" : JSON.stringify(this.closeFactor),
            "totalCollateral" : JSON.stringify(this.totalCollateral),
            "totalBorrows" : JSON.stringify(this.totalBorrows),                          
            "users" : JSON.stringify(this.users)
        }   
        try {
            fs.writeFileSync(this.fileName, JSON.stringify(result));
        } catch (err) {
            console.error(err);
        } 

        return JSON.stringify(result)
    }    

    getBits(bigNum, startBit, endBit) {
        let output = 0
        for(let i = endBit; i >= startBit ; i--) {
            const divFactor = toBN("2").pow(toBN(i))
            const divNum = toBN(bigNum).div(divFactor)
            const roundDownDivNum = (divNum.div(toBN(2))).mul(toBN(2))
            //console.log(divNum.toString(), roundDownDivNum.toString())
            const bit = divNum.eq(roundDownDivNum) ? 0 : 1
            //console.log({bit})
            output = output * 2 + bit;
        }

        //console.log({output})

        return output
    }

    // this simple cache store token symbol to avoid calling the RPC to get the symbol each time
    // we call the getSupplyBorrow() function
    tokenCache = {};

    async getSupplyBorrow() {
        const currentSupply = {};
        const currentBorrow = {};
        const lendingPoolAddress = await this.lendingPoolAddressesProvider.methods.getLendingPool().call();
        const lendingPool = new this.web3.eth.Contract(Addresses.lendingPoolAbi, lendingPoolAddress)
        const protocolDataProvider = new this.web3.eth.Contract(Addresses.protocolDataProviderAbi, Addresses.protocolDataProviderAddress)
        
        const allMarkets = await this.aaveUserInfo.methods.getReservesList(lendingPool.options.address).call()

        for(const market of allMarkets) {
            let cachedToken = this.tokenCache[market];
            if(!cachedToken) {
                const tokenContract = new this.web3.eth.Contract(Addresses.erc20Abi, market)
                const marketSymbol = await tokenContract.methods.symbol().call()
                const marketDecimals = await tokenContract.methods.decimals().call()
                console.log(`adding symbol ${marketSymbol} with address ${market} and ${marketDecimals} decimals to cache`);
                this.tokenCache[market] = {
                    symbol: marketSymbol,
                    decimals: Number(marketDecimals)
                }

                cachedToken = this.tokenCache[market];
            }

            const reserveData = await protocolDataProvider.methods.getReserveData(market).call();
            const liquidity = reserveData.availableLiquidity;
            const liquidityNorm = normalize(liquidity, cachedToken.decimals);
            const debt = reserveData.totalVariableDebt;
            const debtNorm = normalize(debt, cachedToken.decimals);

            currentSupply[cachedToken.symbol] = liquidityNorm;
            currentBorrow[cachedToken.symbol] = debtNorm;
        }

        return {currentSupply, currentBorrow};
    }

    async initPrices() {
        const lendingPoolAddress = await this.lendingPoolAddressesProvider.methods.getLendingPool().call()
        this.lendingPool = new this.web3.eth.Contract(Addresses.lendingPoolAbi, lendingPoolAddress)

        const oracleAddress = await this.lendingPoolAddressesProvider.methods.getPriceOracle().call()
        this.oracle = new this.web3.eth.Contract(Addresses.aaveOracleAbi, oracleAddress)

        const allMarkets = await this.aaveUserInfo.methods.getReservesList(this.lendingPool.options.address).call()
        this.frozen = await this.aaveUserInfo.methods.getFrozenList(this.lendingPool.options.address).call()

        const unfrozenMarkets = []
        for(let i = 0 ; i < allMarkets.length ; i++) {
            if(this.frozen[i]) continue;
            unfrozenMarkets.push(allMarkets[i])
        }

        this.markets = allMarkets //unfrozenMarkets

        for(const market of this.markets) {
            const cfg = await this.lendingPool.methods.getConfiguration(market).call()
            const ltv = Number(this.getBits(cfg[0], 16, 31)) / 1e4
            const liquidationBonus = this.getBits(cfg[0], 32, 47) / 1e4
            const frozen = this.getBits(cfg[0], 57, 57)

            this.liquidationIncentive[market] = liquidationBonus
            this.collateralFactors[market] = ltv

            const token = new this.web3.eth.Contract(Addresses.erc20Abi, market)
            const lastName = await token.methods.symbol().call()
            this.names[market] = lastName
            const tokenDecimals = await token.methods.decimals().call()
            this.decimals[market] = tokenDecimals

            console.log("calling market price", {market}, {lastName})
            const price = await this.oracle.methods.getAssetPrice(market).call()
            this.oraclePrices[market] = price;
            this.prices[market] = toBN(price).mul(toBN(10).pow(toBN(18 - Number(tokenDecimals))))
            console.log(price.toString())
            console.log("calling market price end")

            this.underlying[market] = market 
            this.closeFactor[market] = 0.5

            const limits = await this.lendingPool.methods.getReserveLimits(market).call()

            const borrowCap = (Number(frozen) === 1) ? 1 : limits.borrowLimit
            const collateralCap = (Number(frozen) === 1) ? 1 : limits.depositLimit

            this.borrowCaps[market] = toBN(borrowCap)
            this.collateralCaps[market] = toBN(collateralCap)

            this.totalCollateral[market] = "0"
            this.totalBorrows[market] = "0"            

            console.log(lastName, borrowCap.toString(), collateralCap.toString(), cfg[0].toString())
            await sleep(3);
        }
    }

    async initPricesQuickly() {
        console.log("get markets")
        const markets = this.markets
        
        console.log("get oracle")
        const oracleAddress = this.oracle.options.address
        const oracleContract = this.oracle

        const calls = []
        for(const market of markets) {
            const call = {}
            call["target"] = oracleAddress
            call["callData"] = oracleContract.methods.getAssetPrice(market).encodeABI()

            calls.push(call)
        }

        const priceResults = await this.multicall.methods.tryAggregate(true, calls).call()  
        //console.log({priceResults})      
        for(let i = 0 ; i < priceResults.length ; i++) {
            const price = this.web3.eth.abi.decodeParameter("uint256", priceResults[i].returnData)
            const tokenDecimals = this.decimals[markets[i]]         

            this.prices[markets[i]] = toBN(price).mul(toBN(10).pow(toBN(18 - Number(tokenDecimals))))            
        }

        this.lastUpdateTime = Math.floor(+new Date() / 1000)
    }


    async heavyUpdate() {
        if(this.userList.length == 0) await this.collectAllUsers()
        await this.updateAllUsers()
    }

    async lightUpdate() {        
        await this.periodicUpdateUsers(this.lastUpdateBlock)
    }

    async main(onlyOnce = false) {
        try {
            console.log("main: starting init price")
            let redo = true;
            while(redo) {
                redo = false;
                try {
                    await this.initPrices()
                }
                catch(err) {
                    console.log("initprices failed, trying again", err)
                    await sleep(5);
                    redo = true;
                }
            }

            const currBlock = await retry(this.web3.eth.getBlockNumber, []) - 10
            await sleep(2);
            const currTime = (await retry(this.web3.eth.getBlock, [currBlock])).timestamp

            if(this.mainCntr % this.heavyUpdateInterval == 0) {
                console.log("heavyUpdate start")
                await this.heavyUpdate()
                console.log('heavyUpdate success')
            } else {
                console.log("lightUpdate start")
                await this.lightUpdate()
                console.log('lightUpdate success')
            }
            
            this.lastUpdateBlock = currBlock
            this.lastUpdateTime = currTime

            // don't  increase cntr, this way if heavy update is needed, it will be done again next time
            console.log("sleeping", this.mainCntr++)
        }
        catch(err) {
            console.log("main failed", {err})
        }

        this.getData()

        if(! onlyOnce) setTimeout(this.main.bind(this), 1000 * 60 * 60) // sleep for 1 hour
    }

    async getFallbackPrice(market) {
        return toBN("0") // todo - override in each market
    }

    async getPastEventsInSteps(contract, key, from, to){
        let totalEvents = []
        for (let i = from; i < to; i = i + this.blockStepInInit) {
            const fromBlock = i
            const toBlock = i + this.blockStepInInit > to ? to : i + this.blockStepInInit
            const fn = (...args) => contract.getPastEvents(...args)
            const events = await retry(fn, [key, {fromBlock, toBlock}])
            totalEvents = totalEvents.concat(events)
        }
        return totalEvents
    }

    async periodicUpdateUsers(lastUpdatedBlock) {
        const accountsToUpdate = []
        const currBlock = await this.web3.eth.getBlockNumber() - 10
        console.log({currBlock})

        // we ignore atokens transfer, and catch it when doing the all users update
        const events = {"Deposit" : ["onBehalfOf"],
                        "Withdraw" : ["user"],        
                        "Borrow" : ["onBehalfOf"],
                        "Repay" : ["user"],
                        "LiquidationCall" : ["user", "liquidator"]}

        const keys = Object.keys(events)
        console.log({keys})
        for (const key of keys) {
            const value = events[key]
            console.log({key}, {value})
            const newEvents = await this.getPastEventsInSteps(this.lendingPool, key, lastUpdatedBlock, currBlock) 
            for(const e of newEvents) {
                for(const field of value) {
                    console.log({field})
                    const a = e.returnValues[field]
                    console.log({a})
                    if(a == undefined) {
                        console.log('user address undefined, ignoring');
                        continue;
                    }
                    if(! accountsToUpdate.includes(a)) accountsToUpdate.push(a)
                }
            }
        }

        console.log({accountsToUpdate})
        for(const a of accountsToUpdate) {
            if(! this.userList.includes(a)) this.userList.push(a)            
        }
        // updating users in slices
        const bulkSize = this.multicallSize
        for (let i = 0; i < accountsToUpdate.length; i = i + bulkSize) {
            const to = i + bulkSize > accountsToUpdate.length ? accountsToUpdate.length : i + bulkSize
            const slice = accountsToUpdate.slice(i, to)
            const fn = (...args) => this.updateUsers(...args)
            await retry(fn, [slice])
        }
    }

    async collectAllUsers() {
        const currBlock = /*this.deployBlock + 5000 * 5 //*/ await this.web3.eth.getBlockNumber() - 10
        console.log({currBlock})
        for(let startBlock = this.deployBlock ; startBlock < currBlock ; startBlock += this.blockStepInInit) {
            console.log({startBlock}, this.userList.length, this.blockStepInInit)

            const endBlock = (startBlock + this.blockStepInInit > currBlock) ? currBlock : startBlock + this.blockStepInInit
            let events
            try {
                // Try to run this code
                events = await this.lendingPool.getPastEvents("Deposit", {fromBlock: startBlock, toBlock:endBlock})
                if(events.code == 429) {
                    throw new Error('rate limited')
                }
                if(events == undefined) {
                    throw new Error('events undefined')
                }
            }
            catch(err) {
                // if any error, Code throws the error
                console.log("call failed, trying again", err.toString())
                startBlock -= this.blockStepInInit // try again
                await sleep(5);
                continue
            }
            for(const e of events) {
                const a = e.returnValues.onBehalfOf
                if(a == undefined ) {
                    console.log('user address undefined, ignoring');
                    continue;
                }
                if(! this.userList.includes(a)) this.userList.push(a)
            }
        }
    }

    async updateAllUsers() {
        const users = this.userList //require('./my.json')
        const bulkSize = this.multicallSize
        for(let i = 0 ; i < users.length ; i+= bulkSize) {
            const start = i
            const end = i + bulkSize > users.length ? users.length : i + bulkSize
            console.log("update", i.toString() + " / " + users.length.toString())
            try {
                await this.updateUsers(users.slice(start, end))
            }
            catch(err) {
                console.log("update user failed, trying again", err)
                i -= bulkSize
                await sleep(5);
            }
        }
    }

    async additionalCollateralBalance(userAddress) {
        return this.web3.utils.toBN("0")
    }

    async updateUsers(userAddresses) {
        // need to get: 1) getUserAccountData
        
        const getUserAccountCalls = []
        console.log("preparing getUserAccountCalls")
        for(const user of userAddresses) {
            const call = {}
            if(user == undefined ) {
                console.log('user address undefined, ignoring');
                continue;
            }
            call["target"] = this.aaveUserInfo.options.address
            call["callData"] = this.aaveUserInfo.methods.getUserInfoFlat(this.lendingPool.options.address, user).encodeABI()
            getUserAccountCalls.push(call)
            //console.log({call})
        
            /*
            console.log("doing a single call")
            const result = await this.aaveUserInfo.methods.getUserInfo(this.lendingPool.options.address, user).call()
            //console.log({result})



            const collaterals = {}
            const debts = {}
            // init all markets to zero debt and collateral
            for(const m of this.markets) {
                collaterals[m] = toBN("0")
                debts[m] = toBN("0")
            }

            for(let i = 0 ; i < result.assets.length ; i++) {
                collaterals[result.assets[i]] = toBN(result.collaterals[i])
                debts[result.assets[i]] = toBN(result.debts[i])
            }

            this.users[user] = {"asset": result.assets, "borrowBalances" : debts, "collateralBalances": collaterals,
                                "succ" : true}

            //this.users[user] = userObj            
            */
        }



        // TODO - revive multicall
        //return

        console.log("getting getUserAccountCalls")
        const getUserAccountResults = await this.multicall.methods.tryAggregate(false, getUserAccountCalls).call({gas:100e6})
        console.log("multicall ended")

        for(let i = 0 ; i < userAddresses.length ; i++) {
            const user = userAddresses[i]
            const result = getUserAccountResults[i]

            //console.log({result})

            const collaterals = {}
            const debts = {}
            // init all markets to zero debt and collateral
            for(const m of this.markets) {
                collaterals[m] = toBN("0")
                debts[m] = toBN("0")
            }
            
            /*
            uint256 totalCollateralETH,
            uint256 totalDebtETH,
            uint256 availableBorrowsETH,
            uint256 currentLiquidationThreshold,
            uint256 ltv,
            uint256 healthFactor*/

            const paramType = ["address[]", "uint256[]", "uint256[]"]

            // console.log('decoding return data for', user);
            const parsedResult = this.web3.eth.abi.decodeParameters(paramType,result.returnData)
            
            const assets = parsedResult["0"]
            const collateral = parsedResult["1"]
            const debt = parsedResult["2"]

            for(let i = 0 ; i < assets.length ; i++) {
                collaterals[assets[i]] = toBN(collateral[i])
                debts[assets[i]] = toBN(debt[i])
            }

            this.users[user] = {"asset": assets, "borrowBalances" : debts, "collateralBalances": collaterals,
                                "succ" : true}
        }
    }
  }

module.exports = Aave


