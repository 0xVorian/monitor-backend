const Web3 = require('web3')
const { toBN, toWei, fromWei } = Web3.utils
const axios = require('axios')
const Addresses = require("./Addresses.js")
const fs = require('fs');

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

class Vesta {
    constructor(web3, network, outputFileName) {
      this.web3 = web3
      this.network = network

      this.multicall = new web3.eth.Contract(Addresses.multicallAbi, Addresses.multicallAddress[network])
      this.vestaParameters = new web3.eth.Contract(Addresses.vestaParametersAbi, Addresses.vestaParametersAddress)
      this.multiTroveGetter = new web3.eth.Contract(Addresses.multiTroveGetterAbi, Addresses.multiTroveGetterAddress)
      this.troveManager = new web3.eth.Contract(Addresses.troveManagerAbi, Addresses.vestaTroveManagerAddress)
      this.vst = new web3.eth.Contract(Addresses.erc20Abi, Addresses.vstAddress)
      this.frax = new web3.eth.Contract(Addresses.erc20Abi, Addresses.fraxAddress)      
      this.gelatoKeeper = new web3.eth.Contract(Addresses.gelatoKeeperAbi, Addresses.gelatoKeeperAddress)
      this.glpVault = new web3.eth.Contract(Addresses.glpVaultAbi, Addresses.glpAddress)
      this.curvefiRouter = new web3.eth.Contract(Addresses.curvfiRouterAbi, Addresses.curvefiRouterAddress)

      this.blockStepInInit = 3000
      this.multicallSize = 100

      this.lastUpdateBlock = 18543000
      this.outputFileName = outputFileName

      this.userList = []
      this.glpAddress = "0x2F546AD4eDD93B956C8999Be404cdCAFde3E89AE"
      this.assets = ["0x0000000000000000000000000000000000000000",
                     "0x8D9bA570D6cb60C7e3e0F31343Efe75AB8E65FB1",
                     /*"0xDBf31dF14B66535aF65AaC99C32e9eA844e14501", renBTC is dead*/
                     "0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a",
                     "0x6C2C06790b3E3E3c38e12Ee22F8183b37a13EE55",
                     this.glpAddress]
      this.markets = this.assets

      this.collateralFactors = {}
      this.borrowCaps = {}
      this.collateralCaps = {}
      this.names = {}
      this.liquidationIncentive = {}
      this.lastUpdateTime = 0
      this.users = {}
      this.prices = {}
      this.decimals = {}
      this.underlying = {}
      this.closeFactor = 0.0
      this.stabilityPoolVstBalance = {}
      this.stabilityPoolGemBalance = {}
      this.bprotocolVstBalance = {}      
      this.bprotocolGemBalance = {}
      this.totalCollateral = {}
      this.totalBorrows = {}
      this.curveFraxBalance = 0.0
      this.curveVstBalance = 0.0

      this.glpData = "not init"
    }

    getData() {
        const result =
        {
            "markets" : JSON.stringify(this.markets),
            "prices" : JSON.stringify(this.prices),
            "lastUpdateTime" : this.lastUpdateTime,
            "liquidationIncentive" : this.liquidationIncentive,
            "collateralFactors" : JSON.stringify(this.collateralFactors),
            "names" : JSON.stringify(this.names),
            "borrowCaps" : JSON.stringify(this.borrowCaps),
            "collateralCaps" : JSON.stringify(this.collateralCaps),
            "decimals" : JSON.stringify(this.decimals),
            "underlying" : JSON.stringify(this.underlying),
            "closeFactor" : JSON.stringify(this.closeFactor),
            "stabilityPoolVstBalance" : JSON.stringify(this.stabilityPoolVstBalance),
            "stabilityPoolGemBalance" : JSON.stringify(this.stabilityPoolGemBalance),
            "bprotocolVstBalance" : JSON.stringify(this.bprotocolVstBalance),
            "bprotocolGemBalance" : JSON.stringify(this.bprotocolGemBalance),
            "curveFraxBalance" : JSON.stringify(this.curveFraxBalance),
            "curveVstBalance" : JSON.stringify(this.curveVstBalance),
            "totalCollateral" : JSON.stringify(this.totalCollateral),
            "totalBorrows" : JSON.stringify(this.totalBorrows),
            "glpData" : JSON.stringify(this.glpData),                     
            "users" : JSON.stringify(this.users)
        }   
        try {
            fs.writeFileSync(this.outputFileName, JSON.stringify(result));
        } catch (err) {
            console.error(err);
        } 

        return JSON.stringify(result)
    }

    async heavyUpdate() {
        const currBlock = await this.web3.eth.getBlockNumber() - 10
        const currTime = (await this.web3.eth.getBlock(currBlock)).timestamp        

        if(this.userList.length == 0) await this.collectAllUsers()
        await this.updateAllUsers()
    }

    async lightUpdate() {
        const currBlock = await this.web3.eth.getBlockNumber() - 10
        const currTime = (await this.web3.eth.getBlock(currBlock)).timestamp

        await this.periodicUpdateUsers(this.lastUpdateBlock)
        //await this.calcBadDebt(currTime) 
    }

    async main(onlyOnce = false) {
        try {
            await this.initPrices()
            await this.initBProtocol()
            await this.initGLP()
                        
            const currBlock = await this.web3.eth.getBlockNumber() - 10
            const currTime = (await this.web3.eth.getBlock(currBlock)).timestamp

            await this.collectAllUsers()

            this.lastUpdateBlock = currBlock
            this.lastUpdateTime = currTime

            // don't  increase cntr, this way if heavy update is needed, it will be done again next time
            console.log("sleeping", this.mainCntr++)

            console.log("============================")
            console.log(this.getData())            
        }
        catch(err) {
            console.log("main failed", {err})
        }


        if(! onlyOnce) setTimeout(this.main.bind(this), 1000 * 60 * 60) // sleep for 1 hour
    }

    async initPrices() {
        console.log("get price feed address")
        const priceFeedAddress = await this.vestaParameters.methods.priceFeed().call()
        this.priceFeed = new this.web3.eth.Contract(Addresses.priceFeedAbi, priceFeedAddress)

        console.log("get stability pool manager address")
        const stabilityPoolManagerAddress = await this.troveManager.methods.stabilityPoolManager().call()
        this.stabilityPoolManager = new this.web3.eth.Contract(Addresses.stabilityPoolManagerAbi, stabilityPoolManagerAddress)

        this.decimals[Addresses.vstAddress] = 18
        this.underlying[Addresses.vstAddress] = Addresses.vstAddress
        this.names[Addresses.vstAddress] = "VST"
        this.prices[Addresses.vstAddress] = 
            toBN(
                (await this.curvefiRouter.methods.get_best_rate(
                    Addresses.vstAddress,
                    Addresses.fraxAddress,
                    toWei("1000")
                ).call())["1"]
            ).div(toBN("1000"))

        for(const market of this.assets) {
            console.log({market})

            console.log("getting liquidation incentive")
            this.liquidationIncentive[market] = 
                (Number(fromWei(await this.vestaParameters.methods.BonusToSP(market).call())) + 1).toString()

            console.log("getting MCR")
            const collateralFactor = await this.vestaParameters.methods.MCR(market).call()

            this.closeFactor = 1

            this.collateralFactors[market] = 1 / Number(fromWei(collateralFactor))

            console.log("getting market price")

            this.borrowCaps[market] = toBN(await this.vestaParameters.methods.vstMintCap(market).call())
            this.collateralCaps[market] = "0"

            const stabilitypoolAddress = await this.stabilityPoolManager.methods.getAssetStabilityPool(market).call()
            console.log("getting vst balance of stability pool")
            this.stabilityPoolVstBalance[market] = toBN(await this.vst.methods.balanceOf(stabilitypoolAddress).call())
            console.log("getting market balance")
            

            if(market === "0x0000000000000000000000000000000000000000") {
                this.decimals[market] = 18
                this.underlying[market] = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
                this.names[market] = "ETH"

                this.stabilityPoolGemBalance[market] = toBN(await this.web3.eth.getBalance(stabilitypoolAddress))
            }
            else {
                console.log("getting underlying")
                const underlying = market
                const token = new this.web3.eth.Contract(Addresses.erc20Abi, underlying)
                this.decimals[market] = Number(await token.methods.decimals().call())
                this.underlying[market] = underlying
                console.log("getting market name start")
                this.names[market] = await token.methods.symbol().call()

                this.stabilityPoolGemBalance[market] = toBN(await token.methods.balanceOf(stabilitypoolAddress).call())                
            }

            const price = await this.priceFeed.methods.fetchPrice(market).call()
            this.prices[market] = toBN(price).mul(toBN(10).pow(toBN(18 - Number(this.decimals[market]))))            

            console.log(market, price.toString(), fromWei(collateralFactor), this.names[market])

            this.totalCollateral[market] = "0"
            this.totalBorrows[market] = "0"
        }

        this.curveFraxBalance = Number(fromWei(await this.frax.methods.balanceOf(Addresses.curveVstFraxPoolAddress).call()))
        this.curveVstBalance = Number(fromWei(await this.vst.methods.balanceOf(Addresses.curveVstFraxPoolAddress).call()))

        console.log("init prices: cf ", JSON.stringify(this.collateralFactors), "liquidation incentive ", this.liquidationIncentive)
    }

    async initPricesQuickly() {
        console.log("get markets")
        const markets = this.assets
        
        console.log("get oracle")
        const oracleAddress = this.priceFeed.options.address
        const oracleContract = this.priceFeed

        const calls = []
        for(const market of markets) {
            const call = {}
            call["target"] = oracleAddress
            call["callData"] = oracleContract.methods.fetchPrice(market).encodeABI()

            calls.push(call)
        }

        const priceResults = await this.multicall.methods.tryAggregate(true, calls).call({gas:200e6})  
        for(let i = 0 ; i < priceResults.length ; i++) {
            const price = this.web3.eth.abi.decodeParameter("uint256", priceResults[i].returnData)            

            this.prices[markets[i]] = toBN(price).mul(toBN(10).pow(toBN(18 - Number(this.decimals[markets[i]]))))
        }

        this.prices[Addresses.vstAddress] = 
            toBN(
                (await this.curvefiRouter.methods.get_best_rate(
                    Addresses.vstAddress,
                    Addresses.fraxAddress,
                    toWei("1000")
                ).call())["1"]
            ).div(toBN("1000"))

        this.lastUpdateTime = Math.floor(+new Date() / 1000)        
    }

    async initBProtocol() {
        for(let i = 0 ; i < this.assets.length ; i++) {
            if(this.assets[i] === this.glpAddress) {
                // GLP is not supported by bprotocol yet
                this.bprotocolGemBalance[this.glpAddress] = toBN("0")
                this.bprotocolVstBalance[this.glpAddress] = toBN("0")

                continue
            }

            const bammAddress = await this.gelatoKeeper.methods.bamms(i).call()
            console.log({bammAddress})
            const bammContract = new this.web3.eth.Contract(Addresses.bammAbi, bammAddress)
            
            const market = await bammContract.methods.collateral().call()
            const gemBalance = await bammContract.methods.getCollateralBalance().call()
            const spAddress = await bammContract.methods.SP().call()
            const sp = new this.web3.eth.Contract(Addresses.stabilityPoolAbi, spAddress)
            const vstBalance = await sp.methods.getCompoundedVSTDeposit(bammAddress).call()

            this.bprotocolGemBalance[market] = toBN(gemBalance)
            this.bprotocolVstBalance[market] = toBN(vstBalance)
            console.log("bprotocol", i, market, "collateral (wei)", gemBalance.toString(10), "vst ($)", fromWei(vstBalance.toString(10)))
        }
    }

    async initGLP() {
        const numAssets = await this.glpVault.methods.allWhitelistedTokensLength().call()
        console.log("num glp assets", numAssets)

        // init a multicall to fetch all assets
        const calls = []
        for(let i = 0 ; i < numAssets ; i++) {
            const call = {}
            call["target"] = this.glpVault.options.address
            call["callData"] = this.glpVault.methods.allWhitelistedTokens(i).encodeABI()
            calls.push(call)
        }

        console.log("calling multi get assets")
        const glpAssetResults = await this.multicall.methods.tryAggregate(true, calls).call({gas: 200e6})
        const glpAssets = []
        const balanceOfCalls = []
        const decimalsCalls = []
        const priceOracleCalls = []
        const utilizationCalls = []
        for(let i = 0 ; i < glpAssetResults.length ; i++) {
            const asset = this.web3.eth.abi.decodeParameter("address", glpAssetResults[i].returnData)
            glpAssets.push(asset)

            // balanceOf
            const balanceOfCall = {}
            balanceOfCall["target"] = asset
            balanceOfCall["callData"] = this.vst.methods.balanceOf(this.glpVault.options.address).encodeABI()
            balanceOfCalls.push(balanceOfCall)

            // decimals
            const decimalsCall = {}
            decimalsCall["target"] = asset
            decimalsCall["callData"] = this.vst.methods.decimals().encodeABI()
            decimalsCalls.push(decimalsCall)            

            // price oracle
            const priceOracleCall = {}
            priceOracleCall["target"] = this.glpVault.options.address
            priceOracleCall["callData"] = this.glpVault.methods.getMaxPrice(asset).encodeABI()
            priceOracleCalls.push(priceOracleCall)

            // utilization
            const utilizationCall = {}
            utilizationCall["target"] = this.glpVault.options.address
            utilizationCall["callData"] = this.glpVault.methods.getUtilisation(asset).encodeABI()
            utilizationCalls.push(utilizationCall)
        }

        console.log({glpAssets})

        console.log("calling multi balance of")
        const balanceOfResults = await this.multicall.methods.tryAggregate(true, balanceOfCalls).call({gas: 200e6})
        console.log("calling multi decimals")
        const decimalsResults = await this.multicall.methods.tryAggregate(true, decimalsCalls).call({gas: 200e6})        
        console.log("calling multi price oracle")
        const priceResults = await this.multicall.methods.tryAggregate(true, priceOracleCalls).call({gas: 200e6})
        console.log("calling multi utilization")
        const utilizationResults = await this.multicall.methods.tryAggregate(true, utilizationCalls).call({gas: 200e6})                

        let totalUsdAmount = 0.0
        let totalUsdUsed = 0.0
        let totalStableUsdAmount = 0.0
        let totalStableUsdUsed = 0.0
        let totalSolidAssetsUsdAmount = 0.0
        let totalSolidAssetsUsdUsed = 0.0


        for(let i = 0 ; i < glpAssets.length ; i++) {
            const balanceOf = this.web3.eth.abi.decodeParameter("uint256", balanceOfResults[i].returnData)
            const decimals = this.web3.eth.abi.decodeParameter("uint256", decimalsResults[i].returnData)
            const price = this.web3.eth.abi.decodeParameter("uint256", priceResults[i].returnData)
            const utilization = this.web3.eth.abi.decodeParameter("uint256", utilizationResults[i].returnData)

            const factor = toBN("10").pow(toBN(decimals - 6))
            const usdValue = Number(fromWei(fromWei(toBN(price).mul(toBN(balanceOf).div(toBN(factor))))))
            const usdValueUsd = (utilization) * usdValue / 1000000

            totalUsdAmount += usdValue
            totalUsdUsed += usdValueUsd

            const asset = glpAssets[i]

            if(Addresses.glpStableAddresses.includes(asset)) {
                totalStableUsdAmount += usdValue
                totalStableUsdUsed += usdValueUsd
            }

            if(Addresses.glpSolidAssetAddresses.includes(asset)) {
                totalSolidAssetsUsdAmount += usdValue
                totalSolidAssetsUsdUsed += usdValueUsd
            }
        }

        this.glpData = {
            "liquidTreasury" : totalUsdAmount - totalUsdUsed,
            "treasuryUtilization" : totalUsdUsed / totalUsdAmount,
            "liquidStableTreasury" : totalStableUsdAmount - totalStableUsdUsed,
            "stableTreasuryUtilization" : totalStableUsdUsed / totalStableUsdAmount,
            "liquidSolidAssetTreasury" : totalSolidAssetsUsdAmount - totalSolidAssetsUsdUsed,
            "solidTreasuryUtilization" : totalSolidAssetsUsdUsed / totalSolidAssetsUsdAmount
        }

        // balanceOf, price oracle, utilization


    }

    async collectAllUsers() {
        const users = {}
        for(const market of this.assets) {
            const count = this.multicallSize
            for(let idx = 0 ; ; idx += count) {
                console.log("doing multi trove call")
                const results = await this.multiTroveGetter.methods.getMultipleSortedTroves(market, idx, count).call()
                console.log("multi trove call ended")                
                console.log(market, idx, results.length)
                const calls = []
                for(const result of results) {
                    const call = {}
                    call["target"] = this.troveManager.options.address
                    call["callData"] = this.troveManager.methods.Troves(result.owner, market).encodeABI()
                    calls.push(call)

                    /*
                    console.log("ori",{result})
                    const userKey = result.owner + "_" + market
                    users[userKey] = {"assets" : [market], "borrowBalances" : [toBN(result.debt)],
                                  "collateralBalances" : [toBN(result.coll)],
                                  "succ" : true}*/
                }

                console.log("doing mcall")
                const troveResults = await this.multicall.methods.tryAggregate(false, calls).call()
                console.log("mcall ended")                
                for(let i = 0 ; i < troveResults.length ; i++) {
                    const user = results[i].owner
                    const troveResult = troveResults[i]
                    /*
                    struct Trove {
                        address asset;
                        uint256 debt;
                        uint256 coll;
                        uint256 stake;
                        Status status;
                        uint128 arrayIndex;
                    }*/
                    const paramsType = ["address", "uint256", "uint256", "uint256", "uint256", "uint128"]
                    const params = this.web3.eth.abi.decodeParameters(paramsType, troveResult.returnData)
                    const debt = params[1]
                    const coll = params[2]

                    const decimalsFactor = toBN(10).pow(toBN(this.decimals[market]))
        
                    const userKey = user + "_" + market

                    const borrowBalances = {}
                    const collateralBalances = {}
                    borrowBalances[Addresses.vstAddress] = toBN(debt)
                    borrowBalances[market] = toBN("0")                    
                    collateralBalances[market] = toBN(coll).mul(decimalsFactor).div(toBN(toWei("1")))
                    collateralBalances[Addresses.vstAddress] = toBN("0")
                    users[userKey] = {"assets" : [market, Addresses.vstAddress], borrowBalances,
                                      collateralBalances,
                                      "succ" : troveResult.succ}                    
                }

                if(results.length < count) break
            }
        }

        this.users = users
    }
  }

module.exports = Vesta



