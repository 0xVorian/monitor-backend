/**
 * compute the liquidity of a token to another, using the reserves of one pool and a target slippage
 *  with the following formula: 
 *  a = (y / e) - x
 *  with :
 *      a = amount of token from we can exchange to achieve target slippage,
 *      y = reserve to,
 *      e = target price and
 *      x = reserve from
 * @param {string} fromSymbol 
 * @param {number} fromReserve 
 * @param {string} toSymbol 
 * @param {number} toReserve 
 * @param {number} targetSlippage 
 * @returns {number} amount of token exchangeable for defined slippage
 */
function computeLiquidityForXYKPool(fromSymbol, fromReserve, toSymbol, toReserve, targetSlippage) {
    console.log(`computeLiquidity: Calculating liquidity from ${fromSymbol} to ${toSymbol} with slippage ${Math.round(targetSlippage * 100)} %`);

    const initPrice = toReserve / fromReserve;
    const targetPrice = initPrice - (initPrice * targetSlippage);
    console.log(`computeLiquidity: initPrice: ${initPrice}, targetPrice: ${targetPrice}`);
    const amountOfFromToExchange = (toReserve / targetPrice) - fromReserve;
    console.log(`computeLiquidity: ${fromSymbol}/${toSymbol} liquidity: ${amountOfFromToExchange} ${fromSymbol}`);
    return amountOfFromToExchange;
}

module.exports = { computeLiquidityForXYKPool };

