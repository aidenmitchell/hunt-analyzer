# Hunt Analyzer

A web application for analyzing and comparing Sublime Security hunt results to improve detection rules.

## Features

- Track multiple hunts and their results
- Categorize messages individually or in bulk as true positives or false positives using list view
- Compare multiple hunts to see improvements in your rules
- Identify eliminated false positives and missing true positives
- Analyze rule effectiveness with metrics and summaries

## Deployment with Docker

The easiest way to deploy Hunt Analyzer is using Docker and docker-compose.

### Prerequisites

- Docker and docker-compose installed on your server
- Tailscale (optional) for secure access

### GitHub Integration with Automatic Updates

This setup uses GitHub Container Registry with GitHub Actions for automatic builds and updates.

1. Fork this repository to your GitHub account

2. Enable GitHub Actions in your repository settings

3. On your Portainer server, create a .env file:
```bash
# Create a .env file for configuration
touch .env
```

4. Configure the .env file with your GitHub username and other settings:
```
GITHUB_USERNAME=yourusername
DOCKER_REGISTRY=ghcr.io
TAG=latest
SUBLIME_API_TOKEN=your_api_token_here
SECRET_KEY=your_random_secret_here
```

5. Create a docker-compose.yml file:
```bash
# Download the docker-compose.yml
curl -O https://raw.githubusercontent.com/yourusername/hunt-analyzer/main/docker-compose.yml
```

6. Deploy using docker-compose or Portainer:
```bash
docker-compose up -d
```

7. Access the application at http://localhost:5000 or through your Tailscale IP.

### To Update

When you push changes to your GitHub repository, GitHub Actions will automatically build a new Docker image. To pull the latest image:

```bash
# Pull latest image
docker-compose pull

# Restart the container with new image
docker-compose up -d
```

You can also setup a webhook in Portainer to automatically redeploy when a new image is published.

### Persistent Data

Your hunt data is stored in the `./data` directory which is mounted as a volume in the Docker container. This ensures your data persists across container restarts.

### Portainer Integration with Auto-Updates

If you're using Portainer with Stacks:

1. Go to Stacks → Add stack
2. Use "Repository" as the build method
3. Configure the following:
   - Repository URL: Your GitHub repository URL
   - Repository reference: main
   - Compose path: docker-compose.yml
   - Environment variables: Add variables from step 4 above
4. Deploy the stack

For automatic updates, you can:

1. In Portainer, go to your stack
2. Click "Enable auto-update"
3. Set a polling interval (e.g., 5 minutes)

This will automatically check for changes in your docker-compose.yml and pull the latest image.

### Stopping and Updating

To stop the application:
```bash
docker-compose down
```

To update to a new version:
```bash
git pull
docker-compose up -d --build
```

## Running Without Docker

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hunt-analyzer.git
cd hunt-analyzer
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
# or
flask run
```

4. Access the application in your browser at http://127.0.0.1:5000

## Usage

1. Enter your Sublime Security API token on the home page, or set it in a .env file (see below)
2. Add hunts to analyze by providing their IDs and names
3. Evaluate messages using the list view by categorizing them individually or in bulk as true or false positives
4. Compare hunts to track your rule improvements

### Using Environment Variables

You can set your API token in a `.env` file to avoid entering it manually each time:

1. Create a file named `.env`:
```bash
touch .env
```

2. Edit the `.env` file and set your Sublime Security API token:
```
SUBLIME_API_TOKEN=your_api_token_here
```

When you start the application, it will automatically use the API token from the `.env` file.

## Storage

The application stores your hunt data in a JSON file in the `data` directory. This allows you to keep your categorizations between sessions. Only your API token is stored in the session and is not persisted to disk.

## License

MIT