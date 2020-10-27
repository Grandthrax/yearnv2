
const YearnDaiCompStratV2 = artifacts.require("./YearnDaiCompStratV2.sol");

const VAULT = '0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C';

module.exports = async function(deployer, network, accounts)  {
  console.log(`Deploying smart contracts to '${network}'.`)

  console.log('account 0', accounts[0]);

  const strategy = await deployer.deploy(YearnDaiCompStratV2, VAULT);

  console.log('Strategy deployed at: ', strategy);
};
