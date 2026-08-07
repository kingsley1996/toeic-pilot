1. Install Claude Plugin:
   - Context7
   - Frontend design
   - Playwright
  
2. Setting.json config
{
    "env": {
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
    },
    "teammateMode": "in-process"
}

3. Prompt create agent team:
"Create an Agent Team to complete the project as defined. Team-members: a Front-end Engineer to work on the frontend, a Backend API Engineer on the backend, a Database Engineer on all DB related code, an AI engineering on the AI layers. While all team-members should work on unit-tests, there should be an Integration Tester team-member that builds and runs end-to-end Playwright tests when ready, reporting issues back to be fixed by the team-members. Finally, a Devops engineer for the Docker container and the script."