# Hunt Analyzer

A web application for analyzing and comparing Sublime Security hunt results to improve detection rules.

> [!WARNING]
> This is in development and is not considered a production application. This software is provided 'as is', without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.

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

### Deployment with Portainer (Recommended)

This application is designed to work seamlessly with Portainer for easy deployment and updates.

1. In your Portainer instance, go to Stacks → Add stack

2. Use the following settings:
   - Name: hunt-analyzer
   - Deployment Type: Repository
   - Repository URL: https://github.com/aidenmitchell/hunt-analyzer.git
   - Repository reference: main
   - Compose path: docker-compose.yml

3. Add these environment variables:
   ```
   SUBLIME_API_TOKEN=your_api_token_here
   SECRET_KEY=generate_a_random_string_here
   ```

4. Click "Deploy the stack"

5. Access the application through your Portainer-managed host at port 5000

6. Enable Auto-Update (optional):
   - In your stack, click "Enable auto update"
   - Set interval to 5 minutes

### Updating Your Deployment

The application uses GitHub Actions to automatically build Docker images whenever changes are pushed to the repository.

**For Portainer with auto-update enabled:**
- Updates happen automatically based on your polling interval
- No manual action required

**For manual updates (Portainer or docker-compose):**
```bash
# Pull latest image
docker-compose pull

# Restart the container with new image
docker-compose up -d
```

### Persistent Data

Your hunt data is stored in a named Docker volume (`hunt_analyzer_data`), which ensures your data persists across container restarts and even container replacements. This data will remain intact even if you:

- Pull new versions of the Hunt Analyzer image
- Recreate the container
- Upgrade the application
- Reboot your server

The data is stored securely in Docker's volume management system and will not be lost unless you explicitly delete the volume.

### Manual Deployment with Docker Compose

If you prefer to deploy directly with docker-compose:

1. Create a directory for the application:
```bash
mkdir -p hunt-analyzer
cd hunt-analyzer
```

Note: You don't need to create a data directory - the application uses a Docker named volume for data persistence.

2. Download the docker-compose.yml file:
```bash
curl -O https://raw.githubusercontent.com/aidenmitchell/hunt-analyzer/main/docker-compose.yml
```

3. Create a .env file (optional):
```bash
echo "SUBLIME_API_TOKEN=your_token_here" > .env
echo "SECRET_KEY=random_secret_key" >> .env
```

4. Start the application:
```bash
docker-compose up -d
```

5. Access at http://localhost:5000 or through your Tailscale IP.

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
