import pytest
from brownie import Wei

@pytest.fixture
def dai(interface):
    yield interface.ERC20('0x6b175474e89094c44da98b954eedeac495271d0f')

@pytest.fixture
def comp(interface):
    yield interface.ERC20('0xc00e94Cb662C3520282E6f5717214004A7f26888')

@pytest.fixture
def gov(accounts):
    yield accounts[0]

@pytest.fixture
def strategist(accounts):
    yield accounts[1]

@pytest.fixture
def rando(accounts):
    yield accounts[9]

@pytest.fixture
def whale(accounts):
    yield accounts.at("0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", force=True)

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
        dai.totalSupply() // 5,  # Debt limit of 20% of token supply 
        dai.totalSupply() // 1000,  # Rate limt of 0.1% of token supply per block
        50,  # 0.5% performance fee for Strategist
        {"from": gov},
    )
    yield strategy

@pytest.fixture
def largerunningstrategy(gov, strategy, dai, vault, whale):

    amount = Wei('500000 ether')
    dai.approve(vault, amount, {'from': whale})
    vault.deposit(amount, {'from': whale})    

    strategy.harvest({'from': gov})
    
    yield strategy

