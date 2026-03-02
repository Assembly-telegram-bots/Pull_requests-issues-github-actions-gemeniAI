import os
import json
import requests
from github import Github

gh_token = os.environ.get("GITHUB_TOKEN")
gemini_key = os.environ.get("GEMINI_API_KEY")
repo_name = os.environ.get("REPOSITORY")
issue_number = int(os.environ.get("ISSUE_NUMBER"))
allowed_user = os.environ.get("ALLOWED_USER").strip().lower()

gh = Github(gh_token)
repo = gh.get_repo(repo_name)
issue = repo.get_issue(number=issue_number)

model_name = "gemini-2.5-flash"
api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"

if issue.user.login.strip().lower() == allowed_user:
    prompt = f"""
    Task: {issue.title}
    Description: {issue.body}

    Return only a raw JSON object with no markdown formatting. The JSON must contain these exact keys:
    "file_path": string,
    "content": string,
    "pr_title": string,
    "pr_body": string
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    
    resp = requests.post(api_url, json=payload, headers=headers)
    resp_data = resp.json()
    
    response_text = resp_data['candidates'][0]['content']['parts'][0]['text'].strip()
    
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    elif response_text.startswith("```"):
        response_text = response_text[3:]
        
    if response_text.endswith("```"):
        response_text = response_text[:-3]
        
    response_text = response_text.strip()
    result = json.loads(response_text)

    branch_name = f"issue-{issue_number}-ai-code"
    main_branch = repo.get_branch(repo.default_branch)
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)

    try:
        file_contents = repo.get_contents(result['file_path'], ref=branch_name)
        repo.update_file(
            path=result['file_path'],
            message=f"Update {result['file_path']}",
            content=result['content'],
            sha=file_contents.sha,
            branch=branch_name
        )
    except:
        repo.create_file(
            path=result['file_path'],
            message=f"Create {result['file_path']}",
            content=result['content'],
            branch=branch_name
        )

    repo.create_pull(
        title=result['pr_title'],
        body=f"{result['pr_body']}\n\nResolves #{issue_number}",
        head=branch_name,
        base=repo.default_branch
    )

else:
    prompt = f"""
    Проанализируй задачу для репозитория.
    Задача: {issue.title}
    Описание: {issue.body}
    Оцени реализуемость задачи, возможные сложности и предложи краткий план внедрения. Не пиши готовый код.
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    
    resp = requests.post(api_url, json=payload, headers=headers)
    resp_data = resp.json()
    
    response_text = resp_data['candidates'][0]['content']['parts'][0]['text']
    issue.create_comment(response_text)
