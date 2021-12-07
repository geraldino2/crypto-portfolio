import ccxt
import yaml
import requests

from web3.middleware import geth_poa_middleware
from web3 import Web3

cfg=None
contracts_addr=set()

with open("config.yaml") as config_file:
	cfg=yaml.safe_load(config_file)

w3 = Web3(Web3.HTTPProvider(cfg["bsc_address"]))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

def checksum_address(address:str):
	return w3.toChecksumAddress(address.lower())

def normalize_balance(price):
	return float(w3.fromWei(price, "ether"))

def bsc_abi(contract_address:str) -> dict:
	base_url = "https://api.bscscan.com/api"
	params = dict()
	params["module"] = "contract"
	params["action"] = "getabi"
	params["address"] = contract_address
	params["apikey"] = cfg["bscscan_api_key"]
	req = requests.get(f"https://api.bscscan.com/api", params=params)
	return req.json()["result"]

def pancake_bnb_usdt() -> float:
	pancake_router = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
	bnb_address = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
	usdt_address = "0x55d398326f99059fF775485246999027B3197955"
	pancake_abi = bsc_abi(pancake_router)

	router = w3.eth.contract(address=pancake_router, abi=pancake_abi)
	usd_bnb = router.functions.getAmountsOut(w3.toWei("1", "ether"), [bnb_address, usdt_address]).call()
	return(float(normalize_balance(usd_bnb[1])))

def pancake_price(contract_address:str) -> list:
	pancake_router = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
	bnb_address = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
	usdt_address = "0x55d398326f99059fF775485246999027B3197955"
	contract_address = checksum_address(contract_address)
	token_abi = bsc_abi(contract_address)
	pancake_abi = bsc_abi(pancake_router)

	router = w3.eth.contract(address=pancake_router, abi=pancake_abi)
	usd_bnb = router.functions.getAmountsOut(w3.toWei("1", "ether"), [bnb_address, usdt_address]).call()
	usd_bnb = normalize_balance(usd_bnb[1])

	token_contract = w3.eth.contract(address=checksum_address(contract_address), abi=token_abi)
	decimals = token_contract.functions.decimals().call()

	try:
		txn = router.functions.getAmountsOut(10**decimals, [contract_address, bnb_address]).call()
		bnb_token = normalize_balance(txn[1])
		usd_token = bnb_token*usd_bnb
	except: #bnb pair not found, usdt pair may exist
		try:
			txn = router.functions.getAmountsOut(10**decimals, [contract_address, usdt_address]).call()
			usd_token = normalize_balance(txn[1])
			bnb_token = usd_token/usd_bnb
		except: #neither usdt nor bnb pairs exist
			return [None, None]
	return [bnb_token, usd_token]

with open("bep20_contracts") as bep20_contracts_file:
	for contract_address in bep20_contracts_file.read().split("\n"):
		contracts_addr.add(contract_address)

subtotal=0
print("BSC")
print("-"*40)
balance = normalize_balance(w3.eth.get_balance(cfg["wallet_address"]))
bnb_usdt_price = pancake_bnb_usdt()
usd_balance = balance*bnb_usdt_price
subtotal += float(usd_balance)
print(f"BNB (${round(bnb_usdt_price,8)})")
print(f"{round(balance,8)} = ${round(usd_balance,3)}")
for contract_address in contracts_addr:
	abi = bsc_abi(contract_address)
	contract = w3.eth.contract(address=checksum_address(contract_address), abi=abi)
	balance = contract.functions.balanceOf(checksum_address(cfg["wallet_address"])).call()
	symbol = contract.functions.symbol().call().upper()
	balance = normalize_balance(balance)
	if(balance>0):
		usd_price = pancake_price(contract_address)[1]
		usd_balance = usd_price*balance
		subtotal += float(usd_balance)
		print(f"{symbol} (${round(usd_price,8)})")
		print(f"{round(balance,8)} = ${round(usd_balance,3)}")

exchange_id="binance"
exchange_class=getattr(ccxt, exchange_id)
binance=exchange_class({
    "apiKey": cfg["binance_api_key"],
    "secret": cfg["binance_secret_key"],
})
print("-"*40)
print("Binance")
print("-"*40)
balances=binance.fetchBalance()
for key in balances["total"]:
	if(key=="NFT"):
		continue
	if(balances["total"][key]>0):
		price=float(binance.fetchTicker(f"{key}/USDT")["info"]["lastPrice"])
		balance=balances['total'][key]
		print(f"{key} (${round(price,8)})")
		print(f"{round(balance,8)} = ${round(balance*price,3)}")
		subtotal += float(balance*price)
print("-"*40)
print(f"Subtotal: ${subtotal}\n")
