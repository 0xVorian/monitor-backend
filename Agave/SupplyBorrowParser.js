const Web3 = require('web3')
const Aave = require("./AaveParser.js")
const Addresses = require("./Addresses.js")
const fs = require("fs");

let aave
async function FetchSupplyBorrow() {

    // agave protocol data provider https://gnosisscan.io/address/0xe6729389dea76d47b5bcb0ba5c080821c3b51329#readContract
    try {
        const filename = 'agave_supply_borrow.json';
        console.log(`deleting old file ${filename}`);
        fs.rmSync(filename, {
            force: true
        });
        console.log('getting supply / borrow');
        const supplyBorrow = await aave.getSupplyBorrow();
        console.log('got supply / borrow', supplyBorrow);
        fs.writeFileSync(filename, JSON.stringify(supplyBorrow, null, 2));
        console.log(`file written to ${filename}`);
    }
    catch(error) {
        console.log(error, "will try again in 10 minutes")
    }

    console.log("sleeping for 10 minute")
    setTimeout(FetchSupplyBorrow, 1000 * 60 * 10)
}

async function SupplyBorrowFetcher() {
    const web3 = new Web3("https://rpc.gnosis.gateway.fm")    
    aave = new Aave(Addresses.agaveAddress, "GNOSIS", web3)

    await FetchSupplyBorrow(aave)
}

SupplyBorrowFetcher()

