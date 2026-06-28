---
description: Compare one product across Amazon Japan, Rakuten, Yahoo Shopping, and Google Shopping, including logged-in points and current discounts
argument-hint: <product URL or product name/model>
---

# Compare Japanese Shopping Prices

Compare the product from `$ARGUMENTS` across Japanese shopping sites and produce a concise price table like:

| Platform | Logged-in price | Points/reward | Current discount/coupon | Notes |
|---|---:|---:|---|---|

## Inputs

The user may provide:

- A product URL, such as Amazon Japan, Rakuten, Yahoo Shopping, manufacturer site, BicCamera, Yodobashi, or Google Shopping.
- A model number, JAN, ASIN, or product name.

If the input is a URL, open it first and identify the exact product. If the URL is Amazon, extract the ASIN and verify whether the ASIN maps to the product the user thinks it is. Watch for similarly named products with different capacity, version, color, cable type, or model number.

## Browser Preference

Use the user's already logged-in in-app browser if it is available. This is important because points, coupons, membership rewards, PayPay/Rakuten/Amazon card rewards, and delivery settings can change after login.

If the in-app browser is not open or cannot be controlled, use normal web lookup and clearly mark the result as public/non-personalized.

Do not make purchases, add items to cart, claim/redeem coupons, submit forms, change account settings, or save payment/shipping information. Reading product pages, search results, point details, and coupon descriptions is allowed.

## Required Process

1. **Identify the product**
   - Confirm product title, brand, model number/JAN/ASIN when available, capacity, color, and distinguishing features.
   - State the product identity before comparing if there is ambiguity.

2. **Check Amazon Japan**
   - Open the product URL if the input is Amazon, otherwise search Amazon Japan for the exact model.
   - Capture price, points, coupon/discount/limited-time sale, stock status, seller, and shipper.
   - If points include Amazon Mastercard or Prime Mastercard bonuses, say so.

3. **Check Rakuten Japan**
   - Prefer the official store when available, but include cheaper confirmed same-product offers.
   - Capture price, shipping, expected points, point multiplier, campaign/coupon details, and sale period if shown.
   - Note that SPU, entries, shop-around campaigns, and card status may affect the displayed points.

4. **Check Yahoo! Shopping Japan**
   - Search Yahoo Shopping for the exact model/JAN/product name.
   - Capture price, PayPay points, coupons, campaign bonus, shipping, store, and whether the user is logged in/PayPay-linked if visible.
   - If no exact official/new listing appears, say "no confirmed exact new listing found" rather than forcing a related product.

5. **Check Google Shopping Japan**
   - Search Google Shopping for the exact model.
   - Sort or filter by lowest price when possible.
   - Identify any confirmed same-product new retail option cheaper than the three main platforms.
   - Separate used/auction/flea-market listings from new retail listings.

6. **Compute practical winner**
   - Compare both raw price and estimated net price after points.
   - Do not overstate points as cash unless the platform explicitly treats them as currency. Phrase as "rough effective price if you value points at 1 point = 1 yen."

## Output Format

Answer in Traditional Chinese unless the user asks otherwise.

Start with:

- Product identity line
- Lookup timestamp with date and time zone when available
- A note if results are logged-in personalized

Then provide the comparison table:

| 平台 | 登入後價格 | 點數/回饋 | 促銷/折扣 | 備註 |
|---|---:|---:|---|---|

After the table, include:

- **結論**: best raw price and best estimated net price
- **Google Shopping cheaper options**: list any cheaper confirmed same-product new retail offers, or say none found
- **Caveats**: short notes about coupons, campaign entries, used listings, stock, and account-specific points
- Source links for pages used

Keep the final answer compact and decision-oriented. If a site blocks automation or requires manual verification/CAPTCHA, ask the user to handle that step in the browser and continue afterward.
