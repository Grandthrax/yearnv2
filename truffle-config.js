/*
 * NB: since truffle-hdwallet-provider 0.0.5 you must wrap HDWallet providers in a 
 * function when declaring them. Failure to do so will cause commands to hang. ex:
 * ```
 * mainnet: {
 *     provider: function() { 
 *       return new HDWalletProvider(mnemonic, 'https://mainnet.infura.io/<infura-key>') 
 *     },
 *     network_id: '1',
 *     gas: 4500000,
 *     gasPrice: 10000000000,
 *   },
 */
require('dotenv').config();

const Web3 = require('web3');

const web3 = new Web3();
//const HDWalletProvider = require('truffle-hdwallet-provider');

// defaults
const DEFAULT_ADDRESS_COUNT = 10;
const DEFAULT_GAS_WEI = '4600000';
const DEFAULT_ADDRESS_INDEX = '0';
const DEFAULT_GAS_GWEI_PRICE = '20';

const mnemonic = process.env.MNEMONIC;
const infuraKey = process.env.WEB3_INFURA_PROJECT_ID;
const etherscanApiKey = process.env.ETHERSCAN_TOKEN;
const addressCount = process.env.ADDRESS_COUNT || DEFAULT_ADDRESS_COUNT;
const gas = process.env.GAS_WEI || DEFAULT_GAS_WEI;
const gasPrice = process.env.GAS_PRICE_GWEI || DEFAULT_GAS_GWEI_PRICE;
const defaultAddressIndex = process.env.DEFAULT_ADDRESS_INDEX || DEFAULT_ADDRESS_INDEX


module.exports = {
	web3: Web3,
	mocha: {
		enableTimeouts: false,
	},
	compilers: {
		solc: {
			version: "0.6.12",
			settings: {
				optimizer: {
					enabled: true,
					runs: 200
				},
			},
		}
	},
	api_keys: {
		etherscan: etherscanApiKey
	},
	plugins: [
		'truffle-plugin-verify'
	],
	networks: {
		geth: {
			host: 'localhost',
			port: 8045,
			network_id: '*'
		},
		ganache: {
			host: '127.0.0.1',
			port: 8545,
			network_id: 5777,
			confirmations: 0,
			timeoutBlocks: 50,
			skipDryRun: true
		},
		coverage: {
			host: "127.0.0.1",
			network_id: "*",
			port: 8555,		// <-- If you change this, also set the port option in .solcover.js.
			gas: 0xfffffffffff,	// <-- Use this high gas value
			gasPrice: 0x01	// <-- Use this low gas price
		},
		infuraRopsten: {
			url: 'https://ropsten.infura.io/v3/${infuraKey}',
			gas: gas,
			gasPrice: web3.utils.toWei(gasPrice, 'gwei'),
			network_id: '4',
			skipDryRun: true
		},
		infuraMainnet: {
			url: 'https://ropsten.infura.io/v3/${infuraKey}',
			gas: gas,
			gasPrice: web3.utils.toWei(gasPrice, 'gwei'),
			network_id: '1',
			skipDryRun: false
		},
	}
};