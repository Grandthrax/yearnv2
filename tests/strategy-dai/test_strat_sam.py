from itertools import count
from brownie import Wei, reverts
from useful_methods import stateOfStrat, stateOfVault, deposit,wait, withdraw, harvest
import brownie


def test_strat_sam(accounts, interface, web3, chain, Vault, YearnDaiCompStratV2):
    gov = accounts[0]
    print(gov)
    strategist_and_keeper = accounts[1]
    print(strategist_and_keeper)
    
    dai = interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')
    comp = interface.ERC20('0xc00e94Cb662C3520282E6f5717214004A7f26888')
    
    ydai = interface.ERC20('0x16de59092dae5ccf4a1e6439d611fd0653f0bd01')
    whale = accounts.at("0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", force=True)

    # Deploy the Vault
    vault = gov.deploy(
        Vault, dai, gov, gov, "Yearn DAI v2", "y2DAI"
    )

    assert vault.governance() == gov
    assert vault.guardian() == gov
    assert vault.rewards() == gov
    assert vault.token() == dai

    # Deploy the Strategy
    strategy = strategist_and_keeper.deploy(YearnDaiCompStratV2, vault)

    # Addresses
    assert strategy.strategist() == strategist_and_keeper
    assert strategy.keeper() == strategist_and_keeper
    assert strategy.want() == vault.token()
    stateOfStrat(strategy,dai)
    
    # Add strategy to the Vault
    assert vault.strategies(strategy) == [0, 0, 0, 0, 0, 0, 0]

    _debtLimit = Wei('1000000 ether')
    _rateLimit =  Wei('1000000 ether')

    vault.addStrategy(strategy, _debtLimit, _rateLimit, 50, {"from": gov})

    assert vault.strategies(strategy) == [
        50,
        web3.eth.blockNumber,
        _debtLimit,
        _rateLimit,
        web3.eth.blockNumber,
        0,
        0,
    ]

    print(strategy._predictCompAccrued(), ' comp prediction')

    # Nothing was reported yet from the strategy
    assert vault.expectedReturn(strategy) == 0
    stateOfStrat(strategy,dai)

    depositLimit = Wei('500000 ether')
    vault.setDepositLimit(depositLimit, {"from": gov})
    assert vault.depositLimit() == depositLimit 
    
    # Provide funds to the Vault from whale
   
    # Test first with simply 5k as it is the current rate DAI/block

    amount = Wei('100000 ether')
    deposit(amount,whale, dai, vault )
    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)



    # Call harvest in Strategy only when harvestTrigger() --> (true)
    harvest(strategy, strategist_and_keeper)

   # assert( !strategy.harvestTrigger(0, {'from': strategist_and_keeper}))
    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    # now lets see 90k

    amount = Wei('320000 ether')
    deposit(amount,whale, dai, vault )
    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)
    
    harvest(strategy, strategist_and_keeper)

    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    # Claim COMP and check balance in strategy -> for testing _claimComp() needs to be public
    #strategy._claimComp({'from': strategist_and_keeper})
    #comp_balance = comp.balanceOf(strategy)

    #print(comp_balance.to('ether'), 'comp claimed')

    # Call harvest in Strategy only when harvestTrigger() --> (true)
    #harvest(strategy, strategist_and_keeper)


    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    #withdraw(1, strategy, whale, dai, vault)
    #vault.setEmergencyShutdown(True, {"from": gov})

    
    
    while strategy.harvestTrigger(0) == False:
         wait(25, chain)
         print(strategy._predictCompAccrued().to('ether'), ' comp prediction')

    #print('Emergency Exit')
    #strategy.setEmergencyExit({"from": gov})

    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    harvest(strategy, strategist_and_keeper)

    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    ##test migration
    print('test migration')
    strategy2 = strategist_and_keeper.deploy(YearnDaiCompStratV2, vault)
    vault.migrateStrategy(strategy,strategy2,  {"from": gov})

    print('old strat')
    stateOfStrat(strategy,dai)
    stateOfVault(vault,strategy)

    print('new strat')
    stateOfStrat(strategy2,dai)
    stateOfVault(vault,strategy2)

    withdraw(1, whale, dai, vault)
    stateOfStrat(strategy2,dai)
    stateOfVault(vault,strategy2)

    amount = Wei('320000 ether')
    deposit(amount,whale, dai, vault )
    stateOfStrat(strategy2,dai)
    stateOfVault(vault,strategy2)

    harvest(strategy2, strategist_and_keeper)
    stateOfStrat(strategy2,dai)
    stateOfVault(vault,strategy2)

    withdraw(1, whale, dai, vault)
    stateOfStrat(strategy2,dai)
    stateOfVault(vault,strategy2)