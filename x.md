# Twitter/X 内部 API 爬虫修复指南

> 适用场景：配置了 `auth_token` + `ct0` 后仍无法抓取推文的后端工具

---

## 问题根因速览

| 问题 | 错误做法 | 正确做法 |
|------|---------|---------|
| API Endpoint | `api.twitter.com/1.1/...` | `twitter.com/i/api/graphql/{queryId}/...` |
| Authorization | 自己申请的 OAuth token | 固定的浏览器端 Bearer Token |
| CSRF Header | 未传或传错 | `x-csrf-token` = `ct0` 的值 |
| 响应解析 | `statuses[]` REST 格式 | GraphQL 嵌套结构 |
| Query ID | 硬编码 | 可配置 + 定期刷新 |

---

## 一、正确的请求 Header

```http
Authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA
Cookie: auth_token={AUTH_TOKEN}; ct0={CT0}
x-csrf-token: {CT0}
x-twitter-active-user: yes
x-twitter-client-language: en
content-type: application/json
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

> ⚠️ **最常踩的坑**：`x-csrf-token` 的值 = `ct0` 的值，不是 `auth_token`。缺少这个 header 直接 403。

> ⚠️ `Cookie` 必须拼成一整个字符串：`auth_token=xxx; ct0=xxx`，不能分开传。

---

## 二、固定 Bearer Token

Twitter 内部 Web API 用的是所有浏览器客户端共用的固定 Bearer Token，**不是你 OAuth 申请的那个**：

```
AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA
```

---

## 三、正确的 Endpoint

### 搜索推文

```
GET https://twitter.com/i/api/graphql/{SEARCH_QUERY_ID}/SearchTimeline
```

### 必须携带的 `variables` 参数

```json
{
  "rawQuery": "你的搜索词",
  "count": 20,
  "querySource": "typed_query",
  "product": "Latest"
}
```

### 必须携带的 `features` 参数

```json
{
  "rweb_lists_timeline_redesign_enabled": true,
  "responsive_web_graphql_exclude_directive_enabled": true,
  "verified_phone_label_enabled": false,
  "creator_subscriptions_tweet_preview_api_enabled": true,
  "responsive_web_graphql_timeline_navigation_enabled": true,
  "responsive_web_graphql_skip_user_profile_image_extensions_enabled": false,
  "tweetypie_unmention_optimization_enabled": true,
  "responsive_web_edit_tweet_api_enabled": true,
  "graphql_is_translatable_rweb_tweet_is_translatable_enabled": true,
  "view_counts_everywhere_api_enabled": true,
  "longform_notetweets_consumption_enabled": true,
  "tweet_awards_web_tipping_enabled": false,
  "freedom_of_speech_not_reach_the_tweet_result_enabled": true,
  "standardized_nudges_misinfo": true,
  "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": false,
  "interactive_text_enabled": true,
  "responsive_web_text_underlines_enabled": false,
  "longform_notetweets_richtext_consumption_enabled": true,
  "longform_notetweets_inline_media_enabled": false,
  "responsive_web_enhance_cards_enabled": false
}
```

> ⚠️ `features` 缺失或格式错误会导致 400 Bad Request。

---

## 四、GraphQL Query ID 说明

Query ID 是 Twitter 内部标识 GraphQL 操作的字符串，**会定期变化**，当前参考值：

| 操作 | Query ID 参考值 |
|------|----------------|
| SearchTimeline | `nLP0wk09iJZPMQhp0orkdg` |
| UserTweets | `V1ze5q3ijDS1VQLATLIKcA` |
| TweetDetail | `VWFGPVAGkZMGRKGe3GFFnA` |

### 如何获取最新 Query ID

1. 打开 Chrome DevTools → Network 标签
2. 登录 Twitter，执行一次搜索
3. 过滤请求，找到 `SearchTimeline` 的 XHR 请求
4. URL 中 `/graphql/` 后面那段即为当前有效的 Query ID

### 返回 404 的处理

Query ID 过期 → 404。建议将其配置为环境变量：

```env
TWITTER_SEARCH_QUERY_ID=nLP0wk09iJZPMQhp0orkdg
```

---

## 五、响应数据解析路径

GraphQL 返回的结构与 REST API 完全不同：

```
data
└── search_by_raw_query
    └── search_timeline
        └── timeline
            └── instructions[]
                └── (找 type == "TimelineAddEntries")
                    └── entries[]
                        └── content
                            └── itemContent
                                └── tweet_results
                                    └── result
                                        ├── rest_id          # Tweet ID
                                        ├── core.user_results.result.legacy
                                        │   ├── screen_name  # @用户名
                                        │   └── name         # 显示名
                                        └── legacy
                                            ├── full_text    # 推文内容
                                            ├── created_at   # 发布时间
                                            ├── retweet_count
                                            ├── favorite_count
                                            └── reply_count
```

### Python 解析示例

```python
def parse_tweets(response_json):
    tweets = []
    instructions = (
        response_json
        .get("data", {})
        .get("search_by_raw_query", {})
        .get("search_timeline", {})
        .get("timeline", {})
        .get("instructions", [])
    )
    for instruction in instructions:
        if instruction.get("type") != "TimelineAddEntries":
            continue
        for entry in instruction.get("entries", []):
            try:
                result = (
                    entry["content"]["itemContent"]["tweet_results"]["result"]
                )
                legacy = result["legacy"]
                user = result["core"]["user_results"]["result"]["legacy"]
                tweets.append({
                    "id": result["rest_id"],
                    "text": legacy["full_text"],
                    "created_at": legacy["created_at"],
                    "author": user["screen_name"],
                    "retweets": legacy["retweet_count"],
                    "likes": legacy["favorite_count"],
                })
            except (KeyError, TypeError):
                continue
    return tweets
```

---

## 六、完整请求示例（Python）

```python
import httpx
import json
import os

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
AUTH_TOKEN = os.environ["AUTH_TOKEN"]
CT0 = os.environ["CT0"]
QUERY_ID = os.environ.get("TWITTER_SEARCH_QUERY_ID", "nLP0wk09iJZPMQhp0orkdg")

headers = {
    "Authorization": f"Bearer {BEARER}",
    "Cookie": f"auth_token={AUTH_TOKEN}; ct0={CT0}",
    "x-csrf-token": CT0,
    "x-twitter-active-user": "yes",
    "x-twitter-client-language": "en",
    "content-type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

def search_tweets(query: str, count: int = 20) -> list[dict]:
    variables = {
        "rawQuery": query,
        "count": count,
        "querySource": "typed_query",
        "product": "Latest",
    }
    features = {
        "rweb_lists_timeline_redesign_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_the_tweet_result_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
        "interactive_text_enabled": True,
        "responsive_web_text_underlines_enabled": False,
        "longform_notetweets_richtext_consumption_enabled": True,
        "longform_notetweets_inline_media_enabled": False,
        "responsive_web_enhance_cards_enabled": False,
    }
    resp = httpx.get(
        f"https://twitter.com/i/api/graphql/{QUERY_ID}/SearchTimeline",
        headers=headers,
        params={
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        },
        timeout=15,
    )
    resp.raise_for_status()
    return parse_tweets(resp.json())
```

---

## 七、错误码速查

| 状态码 | 原因 | 解决方法 |
|--------|------|---------|
| `400` | `features` 参数缺失或格式错误 | 检查 features JSON 是否完整 |
| `401` | `auth_token` 无效或过期 | 重新从浏览器 Cookie 复制 |
| `403` | `x-csrf-token` 缺失或不等于 `ct0` | 确认 header 设置正确 |
| `404` | GraphQL Query ID 过期 | 从 DevTools 获取最新 Query ID |
| `429` | 请求频率超限 | 降低请求频率，加 delay |

---

## 八、给 Claude Code 的修复 Prompt

直接复制以下内容丢给 Claude Code：

```
我有一个收集 X/Twitter 数据的后端工具，配置了 auth_token 和 ct0 之后无法正常抓取推文。请帮我修复。

## 目标
配置 AUTH_TOKEN 和 CT0 两个环境变量后，能够正常搜索和抓取 X/Twitter 的帖子。

## 核心问题（请对照检查并修复）

**1. API Endpoint 必须用内部 GraphQL，不能用公开 REST API**
- ❌ 错误：api.twitter.com/1.1/search/tweets.json
- ✅ 正确：https://twitter.com/i/api/graphql/{queryId}/SearchTimeline

**2. 请求 Header 必须完整，缺一不可**
Authorization: Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA
Cookie: auth_token={AUTH_TOKEN}; ct0={CT0}
x-csrf-token: {CT0}        ← 值等于 ct0，不是 auth_token
x-twitter-active-user: yes
x-twitter-client-language: en
content-type: application/json
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36

**3. GraphQL Query ID 可能过期**
当前 SearchTimeline 的 queryId 参考值：nLP0wk09iJZPMQhp0orkdg
如果返回 404，说明 queryId 已过期，需要从 twitter.com 的 DevTools Network 中重新抓取。
建议把 queryId 做成环境变量 TWITTER_SEARCH_QUERY_ID。

**4. 响应数据结构是 GraphQL 格式，不是 REST 的 statuses[]**
正确解析路径：
data.search_by_raw_query.search_timeline.timeline.instructions
  → 找 type == "TimelineAddEntries" 的 instruction
  → entries[].content.itemContent.tweet_results.result

**5. features 参数必须完整传入**（见本文档第三节）

## 请执行
1. 找到项目中负责 Twitter/X 数据抓取的代码文件
2. 对照上面 5 个问题逐一检查并修复
3. 确保 AUTH_TOKEN 和 CT0 从环境变量读取
4. 写一个测试：搜索关键词 "AI" 返回 5 条推文，打印 id / author / text
5. 修复完后告诉我每个文件改了什么以及测试结果
```