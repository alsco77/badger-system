import datetime
from enum import Enum
import json
import os
from scripts.systems.digg_system import connect_digg
from scripts.systems.uniswap_system import UniswapSystem
import warnings
import requests
import brownie
import pytest
from brownie import Wei, accounts, interface, rpc
from config.badger_config import badger_config
from dotmap import DotMap
from helpers.constants import *
from helpers.registry import registry
from helpers.gnosis_safe import GnosisSafe, MultisigTxMetadata
from helpers.time_utils import days, hours, to_days, to_timestamp, to_utc_date
from helpers.utils import val
from rich.console import Console
from scripts.systems.badger_system import BadgerSystem, connect_badger
from tabulate import tabulate
from helpers.gnosis_safe import convert_to_test_mode, exec_direct, get_first_owner
from helpers.constants import MaxUint256
from scripts.systems.sushiswap_system import SushiswapSystem
console = Console()

def test_main():
    main()

def Average(lst): 
    return sum(lst) / len(lst) 

def get_average_daily_price(file):
    with open(file + ".json") as f:
        data = json.load(f)

    price_points = []

    for entry in data["data"]["pairHourDatas"]:
        wbtcBal = float(entry["reserve0"])
        diggBal = float(entry["reserve1"])
        wbtcPerDigg = wbtcBal / diggBal
        locals()
        console.print({
            "wbtcBal": wbtcBal,
            "diggBal": diggBal,
            "wbtcPerDigg": wbtcPerDigg,
        })
        price_points.append(wbtcPerDigg)
    
    average_price = Average(price_points)
    console.print("Average for {} is {}".format(file, average_price)) 
    return average_price

    

def main():
    """
    Connect to badger system, and configure multisig for running transactions in local fork without access to accounts
    """

    # Connect badger system from file
    badger = connect_badger("deploy-final.json")
    digg = connect_digg("deploy-final.json")

    # Sanity check file addresses
    expectedMultisig = "0xB65cef03b9B89f99517643226d76e286ee999e77"
    assert badger.devMultisig == expectedMultisig

    # Multisig wrapper
    multi = GnosisSafe(badger.devMultisig, testMode=True)

    # Get price data from sushiswap, uniswap, and coingecko
    digg_usd_coingecko = 41531.72
    btc_usd_coingecko = 32601.13

    digg_per_btc = digg_usd_coingecko / btc_usd_coingecko

    uniTWAP = get_average_daily_price("scripts/oracle/data/uni_digg_hour")
    sushiTWAP = get_average_daily_price("scripts/oracle/data/sushi_digg_hour")
    averageTWAP = Average([uniTWAP, sushiTWAP])

    console.print({
        "uniTWAP": uniTWAP,
        "sushiTWAP": sushiTWAP,
        "averageTWAP": averageTWAP
    })


    supplyBefore = digg.token.totalSupply()

    print("spfBefore", digg.token._sharesPerFragment())
    print("supplyBefore", digg.token.totalSupply())

    marketValue = Wei(str(averageTWAP) + " ether")

    print(marketValue)

    print(int(marketValue * 10 ** 18))

    print("digg_per_btc", digg_per_btc, averageTWAP, marketValue)

    centralizedMulti = GnosisSafe(digg.centralizedOracle)
    
    print(digg.marketMedianOracle.providerReports(digg.centralizedOracle, 0))
    print(digg.marketMedianOracle.providerReports(digg.centralizedOracle, 1))

    print(digg.cpiMedianOracle.providerReports(digg.constantOracle, 0))
    print(digg.cpiMedianOracle.providerReports(digg.constantOracle, 1))

    print(digg.cpiMedianOracle.getData.call())

    sushi = SushiswapSystem()
    pair = sushi.getPair(digg.token, registry.tokens.wbtc)

    uni = UniswapSystem()
    uniPair = uni.getPair(digg.token, registry.tokens.wbtc)

    print("pair before", pair.getReserves())
    print("uniPair before", uniPair.getReserves())

    tx = centralizedMulti.execute(
        MultisigTxMetadata(description="Set Market Data"),
        {
            "to": digg.marketMedianOracle.address,
            "data": digg.marketMedianOracle.pushReport.encode_input(marketValue),
        },
    )
    chain.mine()

    print(tx.call_trace())
    print(tx.events)

    chain.sleep(hours(1.8))
    chain.mine()

    tx = digg.orchestrator.rebase({'from': badger.deployer})
    chain.mine()

    supplyAfter = digg.token.totalSupply()

    print("spfAfter", digg.token._sharesPerFragment())
    print("supplyAfter", supplyAfter)
    print("supplyChange", supplyAfter / supplyBefore)
    print("supplyChangeOtherWay", supplyBefore / supplyAfter )

    print("pair after", pair.getReserves())
    print("uniPair after", uniPair.getReserves())

    # Make sure sync() was called on the pools from call trace or events

    # Call Sync manually as deployer

