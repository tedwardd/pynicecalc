# PyNiceCalc

This project started off as a basic nicehash profitability calculator and has since evolved in to more of a Nicehash marketplace mining management script. The features are pretty sporatically complete as I only really develop features as I need them. Since I usually only mine Scrypt through Nicehash right now, I have only really tested this script against mining orders for Scrypt, it probably doesn't work for other algorithms quite right. I hope to fix this in the future but there are other features I'm working on right now that I want done first.

Currently, the script expects that you create a config.ini (by default in $CWD but can be defined with `--config` at runtime). The example config shows a rough outline of how this config should look. In short, section `[DEFAULT]` is the main stuff and is all required. Each subsequent section is an order number ['xxx-xxx-xxx-xxx'] (where xxx-xxx-xxx-xxx is the order ID) with a single boolean parameter `manage`. For now, if you want the script to dynamically adjust and manage an order based on market conditions, you need to create a block for the order and set `manage` to `True`. If you don't do this, even if you use the `--manage` flag at runtime, the script will ignore your orders and just give you profitability information.

If you have one or more active orders defined in the `config.ini` and you have set `manage=True` for one or more of the order IDs, then the bot will fetch that order's information and compare it against the theoretical profitability for the algorithm as calculated by whattomine.com. By default, we will calculate profitability off of mining the algorithm on Nicehash itself (as if you had the hardware and were connected to the Nicehash pool for the target algorithm). If, for some reason, this information is not what you want, there is a `--coin` flag. You can provide one or more `--coin` arguments, each with a string value representing a coin that mines with the target algorithm. For example `python calculate.py -a scrypt` will show you profitability based on expected returns from Nicehash. If for some reason you don't want to use this, you can specific the coin symbol as the value to a `--coin` argument, for example: `python calculate.py -a scrypt --coin doge` to only pull dogecoin profitability. If you specify multiple symbols with multiple `--coin` flags, it will add the profit for each one together and show you the profitability based on the sum of the symbols provided. For example, `python calculate -a scrypt --coin doge --coin ltc` will add the profitability of both dogecoin and litecoin together for use when determining profitability, instead of using nicehash-scrypt which does approximately the same thing (as of the time of the writing of this document).

One thing to keep in mind, I don't usually have more than one order open at a time. Theoretically, this script should be able to manage more than one open order for the same algorithm but I've never tested it. Use this script to manage your orders at your own risk, especially if you're trying to manage anything that's not a single Scrypt mining order.

# Setup
The project was written with python 3.10.5 in mind, other minor versions of python3 will probably still work but if you hit an issue and you're not on the version defined in `.python-version`, I can't make any promises I'll fix it. To ensure that you don't have issues, install and use pyenv to automatically use the version defined in `.python-version` any time you're in the project directory.

```
$ git clone git@github.com:tedwardd/pynicecalc.git
$ cd pynicecalc
$ pip install -r requirements.txt
```

# Config Example

```
[DEFAULT]
host = https://api2.nicehash.com
organization_id = # Get this from nicehash profile
key = # Nicehash API key
secret = # Nicehash API secret

[xxxx-xxxx-xxxx-xxxx]
manage=True
```