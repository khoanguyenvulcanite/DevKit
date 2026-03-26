# DevKit

full flow summary:
    Slack
    ↓
    OpenClaw
    ↓
    Composio plugin trong OpenClaw
    ↓
    Remote MCP server của m
    ↓
    GitHub API


Setting up:
    OpenClaw setup

uv add "mcp[cli]" httpx

authenticate to github : https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api?apiVersion=2026-03-10 

restAPI endpoints for reposistories: https://docs.github.com/en/rest/repos?utm_source=chatgpt.com&apiVersion=2026-03-10 

integrate github mcp with openclaw : https://composio.dev/toolkits/github/framework/openclaw


https://github.com/ComposioHQ/openclaw-composio-plugin

Preferences:
    MCP : https://modelcontextprotocol.io/docs/develop/connect-remote-servers
    OpenClaw: https://docs.openclaw.ai/
    github mcp server : https://github.com/github/github-mcp-server 

to-do:
    
    connect remote MCP to thirtd party (composio, slack, openclaw)
        - done locally
        -> need to develop full flow chart of how it can work remotely
    PRs bot research (pr summary, documentation generation)
        - havent searched shit
    survey & collect information
        - 4 engineers : 0/4
    
    weekly target
        hieu sau van de 
            nhan noti, them code agent, hieu them ve cac architecture loi cua cac con nay, ngta dung ntn, limitations, cost, latency, capability,

        setup locally
        used by 4 engineers
        target : useful ++++
        other sub-stask in confluence


    key-words:
        gateway architecture
        webhook/cronjob 

        add skills into slack : 
            on https://api.slack.com/apps , add slash command, ex : /review_pr
            create skills inside openclaw : create folder /review_pr inside ~/.openclaw, inside folder 
            /review_pr create SKILLS.md, then paste in the description of the skill.
            restart openclaw gateway, reinstall slack app, and slack 
            --> que : why i cant access other repo details
        slack notification : GitHub Actions chạy theo lịch + Slack Incoming Webhook.
