const Web3 = require('web3')
const Aave = require("./AaveParser.js")
const Addresses = require("./Addresses.js")
const { FetchBalancerLiquidity } = require('./BalancerLiquidityFetcher.js')
const { sleep } = require('../utils/CommonFunctions.js');

async function AgaveParser() {
    const rpcUrl = "https://rpc.gnosis.gateway.fm";

    // const rpcUrl = "https://rpc.gnosis.gateway.fm";
    // const rpcUrl = "https://gnosis.drpc.org";
    // const rpcUrl = "https://gnosis.blockpi.network/v1/rpc/public";
    // const rpcUrl = "https://gnosis.publicnode.com";
    // const rpcUrl = "https://gnosis.api.onfinality.io/public";
    const web3 = new Web3(rpcUrl)    
    const aave = new Aave(Addresses.agaveAddress, "GNOSIS", web3, "data.json")

    while(true) {
        console.log("----------------------------------------")
        console.log("START FETCHING AGAVE DATA")
        await aave.main(true)
        console.log("END FETCHING AGAVE DATA")
        // fs.writeFileSync('aave_saved.json', JSON.stringify({liquidationIncentive: aave.liquidationIncentive, oraclePrices: aave.oraclePrices}));
        console.log("START FETCHING BALANCER LIQUIDITY")
        await FetchBalancerLiquidity(aave, rpcUrl);
        console.log("END FETCHING BALANCER LIQUIDITY")

        console.log(`sleeping 1 hour`);
        console.log("----------------------------------------")
        await sleep(1000 * 3600);
    }
 }

 AgaveParser()
