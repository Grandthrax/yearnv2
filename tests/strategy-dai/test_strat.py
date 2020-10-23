from itertools import count
from brownie import Wei, reverts
import brownie


def test_vault_deployment_and_strategy_harvest(accounts, interface, web3, chain, Vault, YearnDaiCompStratV2):
    gov = accounts[0]
    print(gov)
    strategist_and_keeper = accounts[1]
    print(strategist_and_keeper)

    ychad = accounts[2]
    print(ychad)
    
    dai = interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')
    
    ydai = interface.ERC20('0x16de59092dae5ccf4a1e6439d611fd0653f0bd01')

    # Deploy the Vault
    vault = gov.deploy(
        Vault, dai, gov, ydai, "yearn DAI v2", "yDAI"
    )

    assert vault.governance() == gov
    assert vault.guardian() == gov
    assert vault.rewards() == ydai
    assert vault.token() == dai

    # Deploy the Strategy
    strategy = strategist_and_keeper.deploy(YearnDaiCompStratV2, vault)

    # Addresses
    assert strategy.strategist() == strategist_and_keeper
    assert strategy.keeper() == strategist_and_keeper
    assert strategy.want() == vault.token()
    
    # Add strategy to the Vault
    assert vault.strategies(strategy) == [0, 0, 0, 0, 0, 0, 0]

    vault.addStrategy(strategy, Wei('100000 ether'), Wei('50000 ether'), 50, {"from": ychad})

    assert vault.strategies(strategy) == [
        50,
        web3.eth.blockNumber,
        Wei('100000 ether'),
        Wei('50000 ether'),
        web3.eth.blockNumber,
        0,
        0,
    ]

    # Nothing was reported yet from the strategy
    assert vault.expectedReturn(strategy) == 0
    
    # Provide funds to the Vault from whale
    whale = accounts.at("0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", force=True)
    
    # Test first with simply 50k as it is the current rate DAI/block
    amount = Wei('50000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})
    print('deposit amount:', amount.to('ether'))

    # Call harvest in Strategy only when harvestTrigger() --> (true)
    assert strategy.harvestTrigger(0)
    harvestCondition = strategy.harvestTrigger(0, {'from': strategist_and_keeper})

    if harvestCondition:
        strategy.harvest({'from': strategist_and_keeper})