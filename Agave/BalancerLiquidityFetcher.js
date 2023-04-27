const { BalancerSDK, Swaps } = require('@balancer-labs/sdk');
const { BigNumber } = require('ethers');
const Aave = require("./AaveParser.js")
const { balancerLiquidityConfig } = require('./Addresses.js');
const { normalize } = require('../utils/TokenHelper.js');
const fs = require("fs");
const { roundTo } = require('../utils/NumberHelper.js');

const MAX_POOLS = 10;
const gasPrice = BigNumber.from(0);

/**
 * Compute balancer liquidity for slippage for ETH / USDC and USDC / ETH
 * using the balancer SDK and a binary search algorithm
 * @param {Aave} aave 
 * @param {string} rpcUrl 
 */
async function FetchBalancerLiquidity(aave, rpcUrl) {

    const balancer = new BalancerSDK({
        network: 100, // gnosis
        rpcUrl: rpcUrl,
    });

    const swapsService = balancer.swaps; // Swaps module

    await swapsService.fetchPools();

    const liquidityForSlippage = {};
    for(const [baseSymbol, config] of Object.entries(balancerLiquidityConfig)) {

        const baseConfig = {
            symbol: baseSymbol,
            address: config.address,
            decimals: config.decimals,
            priceUSD: normalize(aave.oraclePrices[config.address], 18)
        }

        for(const quoteSymbol of config.quotes) {
            console.log(`Fetching balancer liquidity for ${baseSymbol} vs ${quoteSymbol}`);
            const quoteConfig = {
                symbol: quoteSymbol,
                address: balancerLiquidityConfig[quoteSymbol].address,
                decimals: balancerLiquidityConfig[quoteSymbol].decimals,
                priceUSD: normalize(aave.oraclePrices[balancerLiquidityConfig[quoteSymbol].address], 18)
        }
            const targetSlippage = roundTo(aave.liquidationIncentive[config.address] - 1, 2);
            const usdVolumeForSlippage = await GetLiquidityForSlippage(baseConfig, quoteConfig, targetSlippage, swapsService);
            console.log(`usdVolumeForSlippage ${baseConfig.symbol}/${quoteConfig.symbol} = $${usdVolumeForSlippage}`);
            
            if(!liquidityForSlippage[baseSymbol]) {
                liquidityForSlippage[baseSymbol] = {}
            }

            liquidityForSlippage[baseSymbol][quoteSymbol] = {
                volume: usdVolumeForSlippage,
                llc: 1 + targetSlippage
            }
        }
    }

    fs.writeFileSync('balancer_volume_for_slippage.json', JSON.stringify(liquidityForSlippage, null, 2));
}

/**
 * 
 * @param {{ symbol: string; address: any; decimals: any; priceUSD: number; }} baseConfig 
 * @param {{ symbol: string; address: any; decimals: any; priceUSD: number; }} quoteConfig 
 * @param {number} targetSlippage 
 * @param {Swaps} swapsService 
 * @returns 
 */
async function GetLiquidityForSlippage(baseConfig, quoteConfig, targetSlippage, swapsService) {
    const targetPriceUSD =  baseConfig.priceUSD - baseConfig.priceUSD * targetSlippage;

    let tryAmount = BigNumber.from(1).mul(BigNumber.from(10).pow(baseConfig.decimals));
    let normalizedTryAmount = normalize(tryAmount, baseConfig.decimals);
    let minAmount = undefined;
    let normalizedMinAmount = 0;
    let maxAmount = undefined;
    let normalizedMaxAmount = Number.POSITIVE_INFINITY;
    while(true) {
        if((normalizedMaxAmount - normalizedMinAmount) * baseConfig.priceUSD < 1000) {
            const targetVolume = (normalizedMaxAmount + normalizedMinAmount) / 2;
            const targetVolumeUSD = targetVolume * baseConfig.priceUSD;
            console.log(`Volume for ${targetSlippage * 100}% slippage for ${baseConfig.symbol}/${quoteConfig.symbol} is ${targetVolume} ${baseConfig.symbol} = $${targetVolumeUSD}`);
            return targetVolumeUSD;
        }

        const normalizedAmountOut = normalize(await GetAmountOut(swapsService, baseConfig.address, tryAmount, quoteConfig.address), quoteConfig.decimals);
        const priceInOut = normalizedAmountOut / normalizedTryAmount;
        const priceUSD = priceInOut * quoteConfig.priceUSD;

        console.log(`[${normalizedMinAmount} ${baseConfig.symbol} <-> ${normalizedMaxAmount} ${baseConfig.symbol}] | Trying with ${normalizedTryAmount} ${baseConfig.symbol} = $${priceUSD} (${normalizedTryAmount} ${baseConfig.symbol} = ${normalizedAmountOut} ${quoteConfig.symbol})`);

        if(priceUSD > targetPriceUSD) {
            // current price is too high, need to try with a superior try amount
            minAmount = tryAmount;

            if(!maxAmount) {
                tryAmount = tryAmount.mul(2);
            } else {
                tryAmount = tryAmount.add(maxAmount).div(2);
            }
        } else {
            // current price is too low, need to lower tryAmount
            maxAmount = tryAmount;
            if(!minAmount) {
                tryAmount = tryAmount.div(2);
            } else {
                tryAmount = minAmount.add(tryAmount).div(2);
            }
        }

        normalizedTryAmount = normalize(tryAmount, baseConfig.decimals);
        if(minAmount) {
            normalizedMinAmount = normalize(minAmount, baseConfig.decimals);
        }
        if(maxAmount) {
            normalizedMaxAmount = normalize(maxAmount, baseConfig.decimals);
        }
    }
}

/**
 * 
 * @param {Swaps} swapsService 
 * @param {string} addressIn 
 * @param {BigNumber} amountIn 
 * @param {string} addressOut 
 */
async function GetAmountOut(swapsService, addressIn, amountIn, addressOut) {
    
    const swapInfo = await swapsService.findRouteGivenIn({
        tokenIn: addressIn,
        tokenOut: addressOut, 
        amount: amountIn,
        gasPrice: gasPrice,
        maxPools: MAX_POOLS,
    });

    return swapInfo.returnAmount;
}

module.exports = { FetchBalancerLiquidity };

// async function test() {
//     await FetchBalancerLiquidity(JSON.parse(fs.readFileSync("aave_saved.json")), "https://rpc.gnosis.gateway.fm");
// }

// // test();