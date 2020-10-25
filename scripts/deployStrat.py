from pathlib import Path
import yaml

from brownie import Token, YearnDaiCompStratV2, accounts, network, web3
from eth_utils import is_checksum_address

PACKAGE_VERSION = yaml.safe_load(
    (Path(__file__).parent.parent / "ethpm-config.yaml").read_text()
)["version"]


def get_address(msg: str) -> str:
    while True:
        val = input(msg)
        if is_checksum_address(val):
            return val
        else:
            addr = web3.ens.address(val)
            if addr:
                print(f"Found ENS '{val}' [{addr}]")
                return addr
        print(f"I'm sorry, but '{val}' is not a checksummed address or ENS")


def main():
    print(f"You are using the '{network.show_active()}' network")
    dev = accounts.load("dev")
    print(f"You are using: 'dev' [{dev.address}]")
    vaultAddress = get_address("vault contract: ")

    print(
        f"""
    Vault Parameters

   version: {PACKAGE_VERSION}
     vault: {vaultAddress}
strategist: {dev}
    """
    )
    if input("Deploy New Strategy? y/[N]: ").lower() != "y":
        return
    print("Deploying Strategy...")
    #0x1fe16de955718cfab7a44605458ab023838c2793 ropsten comp
    # 0xc00e94Cb662C3520282E6f5717214004A7f26888 mainnet comp
    strategy = YearnDaiCompStratV2.deploy('0x1fE84512a4967c1ba48BF787a290E5C68E4bBEe2', '0x1Fe16De955718CFAb7A44605458AB023838C2793',  {'gas_limit': 7900000, 'from': dev})
