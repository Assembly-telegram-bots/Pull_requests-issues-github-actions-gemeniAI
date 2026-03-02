import os
import json
from github import Github
import google.generativeai as genai

gh_token = os.environ.get("GITHUB_TOKEN")
gemini_key = os.environ.get("GEMINI_API_KEY")
repo_name = os.environ.get("REPOSITORY")
issue_number = int(os.environ.get("ISSUE_NUMBER"))
allowed_user = os.environ.get("ALLOWED_USER")

gh = Github(gh_token)
repo = gh.get_repo(repo_name)
issue = repo.get_issue(number=issue_number)

genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-pro')

if issue.user.login == allowed_user:
    prompt = f"""
    Task: {issue.title}
    Description: {issue.body}

    Return only a raw JSON object with no markdown formatting. The JSON must contain these exact keys:
    "file_path": string,
    "content": string,
    "pr_title": string,
    "pr_body": string
    """

    response = model.generate_content(prompt)
    response_text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
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
    
    response = model.generate_content(prompt)
    issue.create_comment(response.text)
