import pytest
from brownie import Wei

@pytest.fixture
def dai(interface):
    yield interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')

@pytest.fixture
def live_vault(Vault):
    yield Vault.at('0xc2cFcfa978a7fae529DC7E9Aa3CDBE7A727452Bc')

@pytest.fixture
def live_strategy(YearnDaiCompStratV2):
    yield YearnDaiCompStratV2.at('0xEb1E2e30944797232C623498c546565a085B0623')

@pytest.fixture
def dai(interface):
    yield interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')

@pytest.fixture
def samdev(accounts):
    yield accounts.at('0xC3D6880fD95E06C816cB030fAc45b3ffe3651Cb0', force=True)

@pytest.fixture
def comp(interface):
    yield interface.ERC20('0xc00e94Cb662C3520282E6f5717214004A7f26888')

@pytest.fixture
def cdai(interface):
    yield interface.CErc20I('0x5d3a536e4d6dbd6114cc1ead35777bab948e3643')

@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

@pytest.fixture
def gov(accounts):
    yield accounts[0]

@pytest.fixture
def whale(accounts, history, web3):
    acc = accounts.at('0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8', force=True)
    yield acc

@pytest.fixture
def strategist(accounts, whale, dai):
    dai.transfer(accounts[1], Wei('10000 ether'), {'from': whale})
    dai.transfer(accounts[0], Wei('10000 ether'), {'from': whale})
    yield accounts[1]

@pytest.fixture
def rando(accounts):
    yield accounts[9]



@pytest.fixture
def vault(gov, dai, Vault):
    # Deploy the Vault
    vault = gov.deploy(
        Vault, dai, gov, gov, "Yearn DAI v2", "y2DAI"
    )
    yield vault

@pytest.fixture
def seededvault(vault, dai, rando):
   # Make it so vault has some AUM to start
    amount = Wei('10000 ether')
    token.approve(vault, amount, {"from": rando})
    vault.deposit(amount, {"from": rando})
    assert token.balanceOf(vault) == amount
    assert vault.totalDebt() == 0  # No connected strategies yet
    yield vault

@pytest.fixture
def strategy(gov, strategist, dai, vault, YearnDaiCompStratV2):
    strategy = strategist.deploy(YearnDaiCompStratV2, vault)

    vault.addStrategy(
        strategy,
        dai.totalSupply(),  # Debt limit of 20% of token supply 
        dai.totalSupply(),  # Rate limt of 0.1% of token supply per block
        50,  # 0.5% performance fee for Strategist
        {"from": gov},
    )
    yield strategy

@pytest.fixture
def largerunningstrategy(gov, strategy, dai, vault, whale):

    amount = Wei('499000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})    

    strategy.harvest({'from': gov})
    
    #do it again with a smaller amount to replicate being this full for a while
    amount = Wei('1000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})   
    strategy.harvest({'from': gov})
    
    yield strategy

@pytest.fixture
def enormousrunningstrategy(gov, largerunningstrategy, dai, vault, whale):
    dai.approve(vault, dai.balanceOf(whale), {'from': whale})
    vault.deposit(dai.balanceOf(whale), {'from': whale})   
   
    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:

        largerunningstrategy.harvest({'from': gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        
    
    yield largerunningstrategy

