There are some basic assumptions required to run backtester.
1. Ensure the Format of your weights and Data is same as the sample ones already present.
2. ⁠Make sure the Date Range and column matches or it will throw error.
3. ⁠It will execute the weights on the open of next of day.
4. ⁠If You dont have data with format. You can run fetch.py then Run backtester.
5. ⁠Just change the INPUT_WEIGHTS and INPUT_FILE variables to address then run.(just INPUT_WEIGHTS for fetch.py)

There are some rules for how backtester handles weights. Ensure your strategy/weights generator generate the weights according to these(on rebalancing dates).
1. New stocks- weights put will be that ratio of cash remaining after selling or diluting any stock.
2. ⁠Retained Stocks- weights should be nan to leave the stock with same capital(untouched).
3. ⁠Removed/Diluted Stocks- weights should be less than before it will assume to cash all invested(only that stock) then take ratio of all cash to invest.(special case- ‘0’ weights to completely sell)
4. ⁠Sum of absolute values of weights should be less than equal to 1 or else it will throw error. 
