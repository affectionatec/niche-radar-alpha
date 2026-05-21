You are analyzing a web application that collects and analyzes startup 
ideas and market requirements from various online sources. 

Please scan the entire project and perform the following analysis:

## 1. PROJECT UNDERSTANDING
First, map out the current architecture:
- List all data source integrations and their collection logic
- Identify the data processing / NLP pipeline (if any)
- Describe the current scoring or ranking mechanism (if any)
- Describe the frontend and how results are surfaced to the user
- List all dependencies in requirements.txt or package.json

## 2. DATA SOURCE GAP ANALYSIS
Current sources: Google Trends, Reddit (PRAW), Hacker News, 
GitHub Trending, YouTube.

Identify what's needed to add these missing high-value sources 
and suggest implementation approach for each:

Priority 1 (Pain point mining - most critical):
- Product Hunt: scrape product comments for feature requests. 
  Use requests + BS4, target producthunt.com/posts (sorted by 
  votes). Focus on comment text containing "wish", "missing", 
  "should also", "would pay".
- G2 / Capterra: scrape 1-3 star reviews for specific software 
  categories. These are the clearest "unmet need" signals.
  Target: g2.com/products/{slug}/reviews, filter by 1-2 stars.
- Twitter/X: integrate with Twitter API v2 (free tier: 500k 
  tweets/month). Search operators: 
  "someone should build" OR "I wish there was" OR 
  "why doesn't [tool] support" OR "still doing this manually"

Priority 2 (Validation signals):
- Indie Hackers: scrape indiehackers.com/products, collect 
  revenue ranges and product descriptions. This validates which 
  niches already have paying customers.
- App Store / Play Store reviews: use app-store-scraper (npm) 
  or google-play-scraper. Focus on 1-2 star reviews in 
  productivity, developer tools, business categories.
- Stack Overflow: use the official API (no key needed for read). 
  Monitor questions tagged [automation], [devops], [cloud] with 
  0 accepted answers and >10 upvotes — these are unsolved 
  developer pain points.

Priority 3 (Chinese market - unique opportunity):
- V2EX: scrape v2ex.com/go/create (创意区) and v2ex.com/go/career
  for Chinese developer pain points. No API, use requests + BS4.
- 少数派 (sspai.com): scrape the "效率" and "工具癖" sections.
- Search Weibo/知乎 for "有没有什么工具" "求一个能" "为什么没有"

## 3. METHODOLOGY ENHANCEMENT
Review the current data processing pipeline and identify where 
to add:

a) Pain Point Scoring (add a score 1-10 for each collected item):
   - Frequency score: how many times does this pain appear 
     across sources?
   - Urgency score: sentiment analysis — are people frustrated 
     or just mildly annoyed? Use VADER or TextBlob.
   - Monetization signal: does the post mention paying, budget, 
     subscription, pricing? +3 points if yes.
   - Competition gap: does a quick search show no good solution 
     exists? Use SerpAPI or DuckDuckGo to auto-check.

b) Deduplication & Clustering:
   - Add sentence-transformers (all-MiniLM-L6-v2) to embed 
     all collected pain points
   - Cluster similar items using DBSCAN or KMeans
   - Show clusters grouped by theme, not raw list

c) Opportunity Validation Pipeline:
   After collecting a pain point, auto-run:
   1. Search Product Hunt for existing solutions
   2. Search G2 for category — how many products, average 
      rating, price range?
   3. Check IndieHackers for similar products with revenue data
   4. Output: "Validated gap" / "Crowded market" / 
      "Expensive incumbents (opportunity)"

d) Trend Velocity:
   - Track same keywords week over week
   - Flag pain points that are growing (mentioned 2x more this 
     week vs last week)
   - Add a "momentum" indicator to the UI

## 4. SPECIFIC SEARCH QUERIES TO IMPLEMENT
For Reddit (PRAW), add these search patterns across relevant 
subreddits (r/SideProject, r/Entrepreneur, r/artificial, 
r/devops, r/sysadmin, r/cscareerquestions):
  "I wish there was"
  "is there a tool that"  
  "we do this manually"
  "still using spreadsheets"
  "paying for [X] but"
  "anyone built something that"

For Hacker News (search via Algolia API — faster than haxor):
  Use: https://hn.algolia.com/api/v1/search?query=
  Target "Ask HN" posts only (story_type=ask_hn)
  Filter: points > 10, num_comments > 5

## 5. UI/UX ENHANCEMENTS
Review the frontend and suggest improvements for:
- A "Pain Point Score" badge on each result (1-10)
- Filter by: Source | Score | Monetization Signal | Trend
- A "Validate This Idea" button that auto-runs the validation 
  pipeline and shows competitive landscape
- A "Save to Shortlist" feature to track promising ideas
- Weekly email digest of top 5 new pain points discovered
- Export to CSV / Notion


## 6. Data Source Configuration Page
Make sure user can configure the data source in a page.
Extract necessary items to a web page and user can configure on the page.
For Example: X, user can input cookie or something else for configure it. Reddit, some information/key need to input.



Please start by reading the project structure, then proceed 
with the analysis above and give a plan