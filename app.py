import os
import json
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import requests
from dotenv import load_dotenv
from diff_match_patch import diff_match_patch

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hunt_analyzer.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('hunt_analyzer')

# Create data directory if it doesn't exist
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_data():
    """Load data from JSON file"""
    data_file = os.path.join(DATA_DIR, 'hunt_data.json')
    
    if not os.path.exists(data_file):
        return {
            'hunts': [],
            'true_positives': {},
            'false_positives': {}
        }
    
    with open(data_file, 'r') as f:
        return json.load(f)

def save_data(data):
    """Save data to JSON file"""
    data_file = os.path.join(DATA_DIR, 'hunt_data.json')
    
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2)
        
def create_html_diff(text1, text2):
    """Create an HTML diff between two strings."""
    if not text1 and not text2:
        return "<em>No MQL source available for both hunts</em>"
    elif not text1:
        return f"<pre style='background-color:#e6ffed;'>{text2}</pre>"
    elif not text2:
        return f"<pre style='background-color:#ffdce0;'>{text1}</pre>"
    
    dmp = diff_match_patch()
    diffs = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diffs)
    
    html = []
    for op, text in diffs:
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if op == 0:  # Equal
            html.append(f"<span>{text}</span>")
        elif op == -1:  # Deletion
            html.append(f"<span style='background-color:#ffdce0;'>{text}</span>")
        elif op == 1:  # Insertion
            html.append(f"<span style='background-color:#e6ffed;'>{text}</span>")
    
    return "<pre>" + "".join(html) + "</pre>"

class HuntAnalyzer:
    def __init__(self, api_token):
        """Initialize the Hunt Analyzer with API token."""
        self.api_token = api_token
        self.base_url = "https://platform.sublime.security/v0"
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_token}",
            "content-type": "application/json"
        }
    
    def get_hunt_results(self, hunt_id):
        """Get results of a hunt job."""
        response = requests.get(
            f"{self.base_url}/hunt-jobs/{hunt_id}/results",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Error getting hunt results: {response.text}")
        
        return response.json().get("message_groups", [])
    
    def get_hunt_details(self, hunt_id):
        """Get details of a hunt job including its time range and MQL source."""
        response = requests.get(
            f"{self.base_url}/hunt-jobs/{hunt_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Error getting hunt details: {response.text}")
        
        return response.json()
    
    def get_subject_from_message_group(self, message_group):
        """Extract subject from a message group."""
        if message_group.get("messages") and len(message_group["messages"]) > 0:
            return message_group["messages"][0].get("subject", "No subject")
        return "No subject"
        
    def parse_timeframe(self, hunt_details):
        """Parse hunt timeframe into a readable format."""
        start_time = hunt_details.get("range_start_time")
        end_time = hunt_details.get("range_end_time")
        
        if not start_time or not end_time:
            return None
        
        try:
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Format in a user-friendly way
            formatted_start = start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            formatted_end = end_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # Calculate duration in both minutes and days
            duration_seconds = (end_dt - start_dt).total_seconds()
            duration_minutes = int(duration_seconds / 60)
            duration_days = round(duration_seconds / (60 * 60 * 24), 1)  # Convert to days with 1 decimal place
            
            return {
                "start_time": start_time,
                "end_time": end_time,
                "formatted_start": formatted_start,
                "formatted_end": formatted_end,
                "duration_minutes": duration_minutes,
                "duration_days": duration_days
            }
        except Exception:
            return None

# Routes
@app.route('/')
def index():
    """Home page with API token input."""
    # Check if API token is in environment variables
    api_token = os.environ.get('SUBLIME_API_TOKEN')
    if api_token:
        # Set the token in session
        try:
            analyzer = HuntAnalyzer(api_token)
            # Just a small request to test if token works
            session['api_token'] = api_token
            flash('API token loaded from environment variables!', 'success')
            return redirect(url_for('hunts'))
        except Exception as e:
            flash(f'Error with environment API token: {str(e)}', 'danger')
    
    return render_template('index.html')

@app.route('/set_token', methods=['POST'])
def set_token():
    """Set the API token."""
    api_token = request.form.get('api_token', '').strip()
    if not api_token:
        flash('API token cannot be empty!', 'danger')
        return redirect(url_for('index'))
    
    # Test token validity
    try:
        analyzer = HuntAnalyzer(api_token)
        # Just a small request to test if token works
        session['api_token'] = api_token
        flash('API token set successfully!', 'success')
        return redirect(url_for('hunts'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/hunts')
def hunts():
    """Show hunt history and entry form."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    data = load_data()
    return render_template('hunts.html', hunts=data.get('hunts', []))

def reprocess_samples_internal(analyzer, data):
    """Internal function to reprocess all samples to ensure hunt stats are accurate."""
    logger.info("Starting reprocess_samples_internal")
    
    hunts = data.get('hunts', [])
    true_positives = data.get('true_positives', {})
    false_positives = data.get('false_positives', {})
    
    logger.debug(f"Reprocessing {len(hunts)} hunts with {len(true_positives)} TPs and {len(false_positives)} FPs")
    
    if not hunts:
        logger.warning("No hunts to reprocess")
        return False
    
    # Create a lookup of which messages appear in which hunts
    message_hunt_map = {}
    hunt_results_cache = {}
    
    # First pass: build the message-to-hunt map
    logger.info("Building message-to-hunt map")
    for hunt in hunts:
        hunt_id = hunt['id']
        logger.info(f"Fetching results for hunt {hunt_id}")
        results = analyzer.get_hunt_results(hunt_id)
        hunt_results_cache[hunt_id] = results
        logger.debug(f"Hunt {hunt_id} has {len(results)} samples")
        
        for msg in results:
            msg_id = msg['id']
            if msg_id not in message_hunt_map:
                message_hunt_map[msg_id] = []
            message_hunt_map[msg_id].append(hunt_id)
    
    logger.info(f"Message-to-hunt map built with {len(message_hunt_map)} unique messages")
    
    # Track stats before and after for logging
    hunt_stats_before = {}
    hunt_stats_after = {}
    
    # Second pass: recount true/false positives for each hunt
    logger.info("Recounting true/false positives for each hunt")
    updated_hunts = []
    for hunt in hunts:
        hunt_id = hunt['id']
        results = hunt_results_cache[hunt_id]
        
        # Save stats before updates for logging
        hunt_stats_before[hunt_id] = {
            'name': hunt.get('name', 'Unknown'),
            'tp_count': hunt.get('true_positives_count', 0),
            'fp_count': hunt.get('false_positives_count', 0),
            'pre_labeled_count': hunt.get('pre_labeled_count', 0),
            'total_new_samples': hunt.get('total_new_samples', 0),
            'labeled_new_samples': hunt.get('labeled_new_samples', 0),
            'unlabeled_count': hunt.get('unlabeled_count', 0),
        }
        
        # Reset counters
        tp_count = 0
        fp_count = 0
        pre_labeled_count = 0
        
        # Count true/false positives for this hunt
        for msg in results:
            msg_id = msg['id']
            if msg_id in true_positives:
                tp_count += 1
                # Check if this was pre-labeled from another hunt
                if true_positives[msg_id]['hunt_id'] != hunt_id:
                    pre_labeled_count += 1
                    logger.debug(f"Message {msg_id} in hunt {hunt_id} is a pre-labeled TP from hunt {true_positives[msg_id]['hunt_id']}")
            elif msg_id in false_positives:
                fp_count += 1
                # Check if this was pre-labeled from another hunt
                if false_positives[msg_id]['hunt_id'] != hunt_id:
                    pre_labeled_count += 1
                    logger.debug(f"Message {msg_id} in hunt {hunt_id} is a pre-labeled FP from hunt {false_positives[msg_id]['hunt_id']}")
        
        # Calculate unlabeled counts (only for new samples)
        total_new_samples = len(results) - pre_labeled_count
        labeled_new_samples = (tp_count + fp_count) - pre_labeled_count
        unlabeled_count = total_new_samples - labeled_new_samples
        
        logger.info(f"Hunt {hunt_id} ({hunt.get('name', 'Unknown')}): {tp_count} TPs, {fp_count} FPs, {pre_labeled_count} pre-labeled, {unlabeled_count} unlabeled")
        
        # Update hunt stats
        hunt_copy = hunt.copy()
        hunt_copy['true_positives_count'] = tp_count
        hunt_copy['false_positives_count'] = fp_count
        hunt_copy['pre_labeled_count'] = pre_labeled_count
        hunt_copy['total_new_samples'] = total_new_samples
        hunt_copy['labeled_new_samples'] = labeled_new_samples
        hunt_copy['unlabeled_count'] = unlabeled_count
        
        # Save stats after updates for logging
        hunt_stats_after[hunt_id] = {
            'name': hunt_copy.get('name', 'Unknown'),
            'tp_count': tp_count,
            'fp_count': fp_count,
            'pre_labeled_count': pre_labeled_count,
            'total_new_samples': total_new_samples,
            'labeled_new_samples': labeled_new_samples,
            'unlabeled_count': unlabeled_count,
        }
        
        # Add timeframe if missing and verify status
        if 'timeframe' not in hunt_copy:
            try:
                logger.debug(f"Fetching timeframe for hunt {hunt_id}")
                hunt_details = analyzer.get_hunt_details(hunt_id)
                
                # Check if the hunt is completed
                hunt_status = hunt_details.get('status', '').upper()
                if hunt_status != "COMPLETED":
                    # Add a status field to the hunt to warn the user
                    hunt_copy['status_warning'] = f'Hunt has status "{hunt_status}" (not COMPLETED)'
                    logger.warning(f"Hunt {hunt_id} has status {hunt_status}, not COMPLETED")
                else:
                    # Only add timeframe data if hunt is completed
                    timeframe = analyzer.parse_timeframe(hunt_details)
                    if timeframe:
                        hunt_copy['timeframe'] = timeframe
                        logger.debug(f"Added timeframe to hunt {hunt_id}")
                    
                    # Add MQL source if not already present
                    if 'mql_source' not in hunt_copy:
                        mql_source = hunt_details.get('source', '')
                        if mql_source:
                            hunt_copy['mql_source'] = mql_source
                            logger.debug(f"Added MQL source to hunt {hunt_id}")
            except Exception as e:
                # Continue if we can't get the timeframe
                logger.error(f"Error fetching timeframe for hunt {hunt_id}: {str(e)}")
                pass
        
        updated_hunts.append(hunt_copy)
    
    # Compare before and after stats
    for hunt_id in hunt_stats_before:
        before = hunt_stats_before[hunt_id]
        after = hunt_stats_after[hunt_id]
        
        # Log only if there were changes
        if (before['tp_count'] != after['tp_count'] or
            before['fp_count'] != after['fp_count'] or
            before['pre_labeled_count'] != after['pre_labeled_count'] or
            before['unlabeled_count'] != after['unlabeled_count']):
            
            logger.info(f"Hunt {hunt_id} ({after['name']}) stats changed:")
            logger.info(f"  TP count: {before['tp_count']} -> {after['tp_count']}")
            logger.info(f"  FP count: {before['fp_count']} -> {after['fp_count']}")
            logger.info(f"  Pre-labeled: {before['pre_labeled_count']} -> {after['pre_labeled_count']}")
            logger.info(f"  Unlabeled: {before['unlabeled_count']} -> {after['unlabeled_count']}")
    
    # Fix any message references to deleted hunts
    logger.info("Fixing message references to deleted hunts")
    fixed_ref_count = 0
    removed_msg_count = 0
    
    for msg_id in list(true_positives.keys()):
        if msg_id in message_hunt_map:
            # If the message exists but references a non-existent hunt
            ref_hunt_id = true_positives[msg_id]['hunt_id']
            if ref_hunt_id not in hunt_results_cache:
                # Assign to the first hunt where it appears
                new_hunt_id = message_hunt_map[msg_id][0]
                logger.info(f"TP message {msg_id} referenced deleted hunt {ref_hunt_id}, reassigning to {new_hunt_id}")
                true_positives[msg_id]['hunt_id'] = new_hunt_id
                fixed_ref_count += 1
        else:
            # If the message doesn't exist in any hunt, remove it
            logger.info(f"Removing TP message {msg_id} as it doesn't exist in any hunt")
            del true_positives[msg_id]
            removed_msg_count += 1
    
    for msg_id in list(false_positives.keys()):
        if msg_id in message_hunt_map:
            # If the message exists but references a non-existent hunt
            ref_hunt_id = false_positives[msg_id]['hunt_id']
            if ref_hunt_id not in hunt_results_cache:
                # Assign to the first hunt where it appears
                new_hunt_id = message_hunt_map[msg_id][0]
                logger.info(f"FP message {msg_id} referenced deleted hunt {ref_hunt_id}, reassigning to {new_hunt_id}")
                false_positives[msg_id]['hunt_id'] = new_hunt_id
                fixed_ref_count += 1
        else:
            # If the message doesn't exist in any hunt, remove it
            logger.info(f"Removing FP message {msg_id} as it doesn't exist in any hunt")
            del false_positives[msg_id]
            removed_msg_count += 1
    
    logger.info(f"Fixed {fixed_ref_count} message references and removed {removed_msg_count} orphaned messages")
    
    # Save updated data
    data['hunts'] = updated_hunts
    data['true_positives'] = true_positives
    data['false_positives'] = false_positives
    save_data(data)
    
    logger.info("Reprocess completed successfully")
    return True

@app.route('/reprocess_samples', methods=['POST'])
def reprocess_samples():
    """Reprocess all samples to ensure hunt stats are accurate."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    # Load data
    data = load_data()
    hunts = data.get('hunts', [])
    
    if not hunts:
        flash('No hunts to reprocess', 'warning')
        return redirect(url_for('hunts'))
    
    try:
        analyzer = HuntAnalyzer(session['api_token'])
        if reprocess_samples_internal(analyzer, data):
            flash('Samples reprocessed successfully. Hunt stats have been updated.', 'success')
        else:
            flash('No hunts to reprocess', 'warning')
        return redirect(url_for('hunts'))
    except Exception as e:
        flash(f'Error reprocessing samples: {str(e)}', 'danger')
        return redirect(url_for('hunts'))
    
@app.route('/clear_data', methods=['POST'])
def clear_data():
    """Clear all hunt data and reset the application."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    # Reset data to empty state
    empty_data = {
        'hunts': [],
        'true_positives': {},
        'false_positives': {}
    }
    save_data(empty_data)
    
    flash('All hunt data has been cleared successfully!', 'success')
    return redirect(url_for('hunts'))

@app.route('/delete_hunt/<hunt_id>', methods=['POST'])
def delete_hunt(hunt_id):
    """Delete a specific hunt while preserving shared sample data."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    # Load data
    data = load_data()
    hunts = data.get('hunts', [])
    true_positives = data.get('true_positives', {})
    false_positives = data.get('false_positives', {})
    
    # Find the hunt to delete
    hunt_to_delete = next((h for h in hunts if h['id'] == hunt_id), None)
    
    if not hunt_to_delete:
        flash('Hunt not found', 'danger')
        return redirect(url_for('hunts'))
    
    # Remove the hunt from the list
    data['hunts'] = [h for h in hunts if h['id'] != hunt_id]
    
    # Check which hunts remain (to preserve shared samples)
    remaining_hunt_ids = [h['id'] for h in data['hunts']]
    
    try:
        analyzer = HuntAnalyzer(session['api_token'])
        
        # Create a cache of hunt results to avoid repeated API calls
        hunt_results_cache = {}
        
        # Get the results for the hunt being deleted
        hunt_results_cache[hunt_id] = analyzer.get_hunt_results(hunt_id)
        message_ids = [msg['id'] for msg in hunt_results_cache[hunt_id]]
        
        # Build a lookup map of which messages appear in which remaining hunts
        message_hunt_map = {}
        
        # Fetch all remaining hunt results in one batch to minimize API calls
        for other_hunt_id in remaining_hunt_ids:
            hunt_results_cache[other_hunt_id] = analyzer.get_hunt_results(other_hunt_id)
            
            # Map each message ID to this hunt
            for msg in hunt_results_cache[other_hunt_id]:
                if msg['id'] not in message_hunt_map:
                    message_hunt_map[msg['id']] = []
                message_hunt_map[msg['id']].append(other_hunt_id)
        
        # Find messages that were labeled in this hunt
        hunt_labeled_messages = []
        for msg_id in true_positives:
            if true_positives[msg_id]['hunt_id'] == hunt_id:
                hunt_labeled_messages.append(msg_id)
                
        for msg_id in false_positives:
            if false_positives[msg_id]['hunt_id'] == hunt_id:
                hunt_labeled_messages.append(msg_id)
        
        # Only process messages that were labeled in this hunt (more efficient)
        for msg_id in hunt_labeled_messages:
            # Check if this message appears in other remaining hunts
            other_hunts_with_msg = message_hunt_map.get(msg_id, [])
            message_in_other_hunts = len(other_hunts_with_msg) > 0
            
            # If message is not in other hunts, remove its categorization
            if not message_in_other_hunts:
                if msg_id in true_positives and true_positives[msg_id]['hunt_id'] == hunt_id:
                    del true_positives[msg_id]
                if msg_id in false_positives and false_positives[msg_id]['hunt_id'] == hunt_id:
                    del false_positives[msg_id]
            
            # If message is in other hunts but was categorized in this hunt,
            # update the hunt_id reference to one of the remaining hunts
            else:
                if msg_id in true_positives and true_positives[msg_id]['hunt_id'] == hunt_id:
                    # Use the first hunt where this message appears
                    true_positives[msg_id]['hunt_id'] = other_hunts_with_msg[0]
                
                if msg_id in false_positives and false_positives[msg_id]['hunt_id'] == hunt_id:
                    # Use the first hunt where this message appears
                    false_positives[msg_id]['hunt_id'] = other_hunts_with_msg[0]
        
        # Save updated data
        data['true_positives'] = true_positives
        data['false_positives'] = false_positives
        save_data(data)
        
        flash(f'Hunt "{hunt_to_delete["name"]}" has been deleted successfully!', 'success')
        return redirect(url_for('hunts'))
    
    except Exception as e:
        flash(f'Error deleting hunt: {str(e)}', 'danger')
        return redirect(url_for('hunts'))

@app.route('/add_hunt', methods=['POST'])
def add_hunt():
    """Add a new hunt to analyze."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    hunt_id = request.form.get('hunt_id', '').strip()
    hunt_name = request.form.get('hunt_name', '').strip()
    
    logger.info(f"Adding new hunt ID: {hunt_id}, Name: {hunt_name}")
    
    if not hunt_id or not hunt_name:
        logger.warning("Hunt ID or name is missing")
        flash('Hunt ID and name are required', 'danger')
        return redirect(url_for('hunts'))
    
    # Load data
    data = load_data()
    hunts = data.get('hunts', [])
    
    # Check if this hunt was already added
    for hunt in hunts:
        if hunt['id'] == hunt_id:
            logger.warning(f"Hunt {hunt_id} already exists as '{hunt['name']}'")
            flash(f'This hunt has already been added as "{hunt["name"]}"', 'warning')
            return redirect(url_for('hunts'))
    
    # Add the hunt to data
    try:
        logger.info(f"Fetching hunt results for {hunt_id}")
        analyzer = HuntAnalyzer(session['api_token'])
        results = analyzer.get_hunt_results(hunt_id)
        logger.info(f"Retrieved {len(results)} samples for hunt {hunt_id}")
        
        true_positives = data.get('true_positives', {})
        false_positives = data.get('false_positives', {})
        
        logger.debug(f"Current database contains {len(true_positives)} true positives and {len(false_positives)} false positives")
        
        # Get hunt details including timeframe and status
        try:
            hunt_details = analyzer.get_hunt_details(hunt_id)
            
            # Check if the hunt is completed
            hunt_status = hunt_details.get('status', '').upper()
            logger.info(f"Hunt {hunt_id} status: {hunt_status}")
            
            if hunt_status != "COMPLETED":
                logger.warning(f"Hunt {hunt_id} has status {hunt_status}, not COMPLETED")
                flash(f'This hunt has status "{hunt_status}" and is not ready for analysis yet. Only import hunts with "COMPLETED" status.', 'danger')
                return redirect(url_for('hunts'))
            
            # Extract MQL source
            mql_source = hunt_details.get('source', '')
            logger.debug(f"Hunt MQL source: {mql_source}")
                
            timeframe = analyzer.parse_timeframe(hunt_details)
            logger.debug(f"Hunt timeframe: {timeframe}")
        except Exception as e:
            # If we can't get the timeframe, continue without it
            timeframe = None
            mql_source = ''
            logger.error(f"Error getting hunt details: {str(e)}")
        
        # Auto-label samples that match existing true/false positives
        tp_count = 0
        fp_count = 0
        
        # Keep track of auto-labeled samples for logging
        auto_labeled_samples = {'tp': [], 'fp': []}
        
        for message_group in results:
            msg_id = message_group['id']
            
            # Check if this message is already in true_positives
            if msg_id in true_positives:
                tp_count += 1
                auto_labeled_samples['tp'].append({
                    'id': msg_id,
                    'subject': analyzer.get_subject_from_message_group(message_group),
                    'original_hunt': true_positives[msg_id]['hunt_id']
                })
            # Check if this message is already in false_positives
            elif msg_id in false_positives:
                fp_count += 1
                auto_labeled_samples['fp'].append({
                    'id': msg_id,
                    'subject': analyzer.get_subject_from_message_group(message_group),
                    'original_hunt': false_positives[msg_id]['hunt_id']
                })
        
        logger.info(f"Auto-labeled {tp_count} true positives and {fp_count} false positives")
        logger.debug(f"Auto-labeled TP samples: {auto_labeled_samples['tp']}")
        logger.debug(f"Auto-labeled FP samples: {auto_labeled_samples['fp']}")
        
        hunt_data = {
            'id': hunt_id,
            'name': hunt_name,
            'total_samples': len(results),
            'true_positives_count': tp_count,
            'false_positives_count': fp_count,
            'pre_labeled_count': tp_count + fp_count,  # Keep track of pre-labeled count
            'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'mql_source': mql_source  # Store the MQL source
        }
        
        # Add timeframe if available
        if timeframe:
            hunt_data['timeframe'] = timeframe
        
        hunts.append(hunt_data)
        
        data['hunts'] = hunts
        save_data(data)
        logger.info(f"Hunt {hunt_id} added to database with {len(results)} samples")
        
        pre_labeled = tp_count + fp_count
        new_samples = len(results) - pre_labeled
        
        if pre_labeled > 0:
            flash(f'Hunt "{hunt_name}" added successfully with {len(results)} samples. ' + 
                  f'{pre_labeled} samples were automatically labeled based on your previous decisions.', 'success')
        else:
            flash(f'Hunt "{hunt_name}" added successfully with {len(results)} samples.', 'success')
        
        # After adding a hunt, reprocess all samples to ensure consistent labeling
        try:
            logger.info("Running reprocess_samples_internal after adding hunt")
            # We already have an analyzer instance
            reprocess_result = reprocess_samples_internal(analyzer, data)
            logger.info(f"Reprocess completed, result: {reprocess_result}")
        except Exception as e:
            logger.error(f"Error reprocessing samples after adding hunt: {str(e)}", exc_info=True)
        
        return redirect(url_for('analyze_hunt', hunt_id=hunt_id))
    except Exception as e:
        logger.error(f"Error adding hunt {hunt_id}: {str(e)}", exc_info=True)
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('hunts'))

@app.route('/analyze/<hunt_id>')
def analyze_hunt(hunt_id):
    """Analyze a specific hunt."""
    logger.info(f"Analyzing hunt {hunt_id}")
    
    if 'api_token' not in session:
        logger.warning("API token not set, redirecting to index")
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    # Load data
    data = load_data()
    
    # Find the hunt
    hunt = next((h for h in data.get('hunts', []) if h['id'] == hunt_id), None)
    
    if not hunt:
        logger.warning(f"Hunt {hunt_id} not found")
        flash('Hunt not found', 'danger')
        return redirect(url_for('hunts'))
    
    logger.info(f"Found hunt {hunt_id}: {hunt.get('name', 'Unknown')}")
    logger.debug(f"Hunt details: {hunt}")
    
    # Get hunt results
    try:
        analyzer = HuntAnalyzer(session['api_token'])
        results = analyzer.get_hunt_results(hunt_id)
        
        # Prepare data for template
        message_groups = []
        true_positives = data.get('true_positives', {})
        false_positives = data.get('false_positives', {})
        
        # Count for real-time accuracy
        tp_count = 0
        fp_count = 0
        
        # Check if this is the first time viewing this hunt
        first_view = True
        if 'pre_labeled_viewed' not in hunt:
            # Get the show_all_messages parameter
            show_all_messages = request.args.get('show_all', '0') == '1'
        else:
            # Hunt was viewed before, use the stored preference
            first_view = False
            show_all_messages = request.args.get('show_all', '0') == '1'
        
        # Process message groups
        for message_group in results:
            msg_id = message_group['id']
            subject = analyzer.get_subject_from_message_group(message_group)
            
            # Determine if it's already categorized
            status = None
            pre_labeled = False
            
            if msg_id in true_positives:
                status = 'true_positive'
                tp_count += 1
                
                # Check if this was labeled in a different hunt
                if true_positives[msg_id]['hunt_id'] != hunt_id:
                    pre_labeled = True
                    
            elif msg_id in false_positives:
                status = 'false_positive'
                fp_count += 1
                
                # Check if this was labeled in a different hunt
                if false_positives[msg_id]['hunt_id'] != hunt_id:
                    pre_labeled = True
            
            # Skip pre-labeled messages unless show_all_messages is true
            if pre_labeled and not show_all_messages:
                continue
                
            # Create message group data
            msg_data = {
                'id': msg_id,
                'subject': subject,
                'status': status,
                'pre_labeled': pre_labeled,
                'message_link': f"https://platform.sublime.security/messages/{msg_id}"
            }
            
            # Add sender info if available
            if message_group.get('messages') and len(message_group['messages']) > 0:
                message = message_group['messages'][0]
                sender_name = message.get('sender', {}).get('display_name', 'Unknown')
                sender_email = message.get('sender', {}).get('email', 'unknown@example.com')
                msg_data['sender'] = f"{sender_name} <{sender_email}>"
                
                recipients = [r.get('email', 'unknown@example.com') for r in message.get('recipients', [])]
                msg_data['recipients'] = recipients[:3]
                msg_data['recipients_count'] = len(recipients)
                
                msg_data['date'] = message.get('created_at', 'Unknown')
            
            # Add flagged rules
            flagged_rules = message_group.get('flagged_rules', [])
            msg_data['rules'] = [rule.get('name') for rule in flagged_rules[:5]]
            msg_data['rules_count'] = len(flagged_rules)
            
            message_groups.append(msg_data)
        
        # Update hunt stats in memory (don't save to disk yet as this is just a view)
        hunt_copy = hunt.copy()
        hunt_copy['true_positives_count'] = tp_count
        hunt_copy['false_positives_count'] = fp_count
        hunt_copy['total_samples'] = len(results)
        
        # Count unlabeled messages (only messages that weren't pre-labeled from other hunts)
        total_pre_labeled = 0
        for message_group in results:
            msg_id = message_group['id']
            if msg_id in true_positives and true_positives[msg_id]['hunt_id'] != hunt_id:
                total_pre_labeled += 1
            elif msg_id in false_positives and false_positives[msg_id]['hunt_id'] != hunt_id:
                total_pre_labeled += 1
        
        # Calculate total unlabeled messages that we care about
        total_new_samples = len(results) - total_pre_labeled
        labeled_new_samples = (tp_count + fp_count) - total_pre_labeled  # Only count labels from this hunt
        hunt_copy['total_new_samples'] = total_new_samples
        hunt_copy['labeled_new_samples'] = labeled_new_samples
        hunt_copy['unlabeled_count'] = total_new_samples - labeled_new_samples
        hunt_copy['pre_labeled_count'] = total_pre_labeled
        
        # Set the show_all_messages flag for the template
        show_all_messages = request.args.get('show_all', '0') == '1'
        
        # Check if counts don't match what's stored - if so, suggest reprocessing
        counts_mismatch = (tp_count != hunt.get('true_positives_count', 0) or 
                           fp_count != hunt.get('false_positives_count', 0) or
                           len(results) != hunt.get('total_samples', 0))
        
        if counts_mismatch:
            logger.warning(f"Count mismatch detected for hunt {hunt_id}:")
            logger.warning(f"  Stored TP count: {hunt.get('true_positives_count', 0)}, Actual: {tp_count}")
            logger.warning(f"  Stored FP count: {hunt.get('false_positives_count', 0)}, Actual: {fp_count}")
            logger.warning(f"  Stored total: {hunt.get('total_samples', 0)}, Actual: {len(results)}")
            logger.warning(f"  Stored pre-labeled: {hunt.get('pre_labeled_count', 0)}")
            logger.warning(f"  Stored unlabeled: {hunt.get('unlabeled_count', 0)}")
            
            # Log detailed information for debugging
            labeled_msgs = set()
            for msg in message_groups:
                if msg.get('status') is not None:
                    labeled_msgs.add(msg.get('id'))
            
            logger.debug(f"Count of message_groups with status: {len(labeled_msgs)}")
            logger.debug(f"Total message_groups: {len(message_groups)}")
            
            # Check if the correct number of messages are displayed in the UI
            if len(message_groups) != len(results) and not show_all_messages:
                skipped_count = len(results) - len(message_groups)
                logger.info(f"UI is filtering {skipped_count} pre-labeled messages with show_all_messages={show_all_messages}")
        
        # Mark that the hunt was viewed, so we remember the user's preference
        if 'pre_labeled_viewed' not in hunt:
            for h in data['hunts']:
                if h['id'] == hunt_id:
                    h['pre_labeled_viewed'] = True
                    save_data(data)  # Save this flag
                    break
            logger.info(f"Marked hunt {hunt_id} as viewed for the first time")
        
        return render_template('analyze.html', 
                              hunt=hunt_copy, 
                              message_groups=message_groups, 
                              counts_mismatch=counts_mismatch, 
                              show_all_messages=show_all_messages)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('hunts'))

@app.route('/categorize', methods=['POST'])
def categorize():
    """Categorize a message as true positive or false positive."""
    if 'api_token' not in session:
        logger.warning("Categorize attempt without API token")
        return jsonify({'status': 'error', 'message': 'API token not set'})
    
    msg_id = request.form.get('msg_id')
    hunt_id = request.form.get('hunt_id')
    subject = request.form.get('subject')
    category = request.form.get('category')
    
    logger.info(f"Categorizing message {msg_id} from hunt {hunt_id} as {category}")
    
    if not all([msg_id, hunt_id, subject, category]):
        logger.warning(f"Missing parameters: msg_id={msg_id}, hunt_id={hunt_id}, subject={subject}, category={category}")
        return jsonify({'status': 'error', 'message': 'Missing required parameters'})
    
    if category not in ['true_positive', 'false_positive']:
        logger.warning(f"Invalid category: {category}")
        return jsonify({'status': 'error', 'message': 'Invalid category'})
    
    # Load data
    data = load_data()
    true_positives = data.get('true_positives', {})
    false_positives = data.get('false_positives', {})
    hunts = data.get('hunts', [])
    
    # Check existing categorization status before change
    was_tp = msg_id in true_positives
    was_fp = msg_id in false_positives
    previous_hunt_id = None
    
    if was_tp:
        previous_hunt_id = true_positives[msg_id]['hunt_id']
    elif was_fp:
        previous_hunt_id = false_positives[msg_id]['hunt_id']
    
    logger.debug(f"Before categorization: msg_id={msg_id}, was_tp={was_tp}, was_fp={was_fp}, previous_hunt_id={previous_hunt_id}")
    
    # Remove from opposite category if needed
    if category == 'true_positive' and msg_id in false_positives:
        logger.info(f"Removing message {msg_id} from false_positives")
        del false_positives[msg_id]
    elif category == 'false_positive' and msg_id in true_positives:
        logger.info(f"Removing message {msg_id} from true_positives")
        del true_positives[msg_id]
    
    # Add to the correct category
    if category == 'true_positive':
        logger.info(f"Adding message {msg_id} to true_positives with hunt_id {hunt_id}")
        true_positives[msg_id] = {'hunt_id': hunt_id, 'subject': subject}
    else:
        logger.info(f"Adding message {msg_id} to false_positives with hunt_id {hunt_id}")
        false_positives[msg_id] = {'hunt_id': hunt_id, 'subject': subject}
    
    # Update hunt stats
    affected_hunts = set()
    affected_hunts.add(hunt_id)
    if previous_hunt_id and previous_hunt_id != hunt_id:
        affected_hunts.add(previous_hunt_id)
    
    hunt_stats_before = {}
    hunt_stats_after = {}
    
    for hunt in hunts:
        if hunt['id'] in affected_hunts:
            hunt_id_to_update = hunt['id']
            
            # Store stats before update
            hunt_stats_before[hunt_id_to_update] = {
                'name': hunt.get('name', 'Unknown'),
                'tp_count': hunt.get('true_positives_count', 0),
                'fp_count': hunt.get('false_positives_count', 0)
            }
            
            # Recount for this hunt
            tp_count = sum(1 for tp in true_positives.values() if tp['hunt_id'] == hunt_id_to_update)
            fp_count = sum(1 for fp in false_positives.values() if fp['hunt_id'] == hunt_id_to_update)
            hunt['true_positives_count'] = tp_count
            hunt['false_positives_count'] = fp_count
            
            # Store stats after update
            hunt_stats_after[hunt_id_to_update] = {
                'name': hunt.get('name', 'Unknown'),
                'tp_count': tp_count,
                'fp_count': fp_count
            }
            
            logger.info(f"Updated hunt {hunt_id_to_update} ({hunt.get('name', 'Unknown')}) stats: TP {hunt_stats_before[hunt_id_to_update]['tp_count']} -> {tp_count}, FP {hunt_stats_before[hunt_id_to_update]['fp_count']} -> {fp_count}")
    
    # Save data
    data['true_positives'] = true_positives
    data['false_positives'] = false_positives
    data['hunts'] = hunts
    save_data(data)
    
    logger.info(f"Categorization complete for message {msg_id} as {category}")
    return jsonify({'status': 'success'})

@app.route('/mass_categorize', methods=['POST'])
def mass_categorize():
    """Categorize multiple messages at once."""
    if 'api_token' not in session:
        logger.warning("Mass categorize attempt without API token")
        return jsonify({'status': 'error', 'message': 'API token not set'})
    
    hunt_id = request.form.get('hunt_id')
    message_ids = request.form.getlist('message_ids[]')
    category = request.form.get('category')
    
    logger.info(f"Mass categorizing {len(message_ids)} messages from hunt {hunt_id} as {category}")
    
    if not hunt_id or not message_ids or not category:
        logger.warning(f"Missing parameters: hunt_id={hunt_id}, message_ids={message_ids}, category={category}")
        return jsonify({'status': 'error', 'message': 'Missing required parameters'})
    
    if category not in ['true_positive', 'false_positive']:
        logger.warning(f"Invalid category: {category}")
        return jsonify({'status': 'error', 'message': 'Invalid category'})
    
    # Load data
    data = load_data()
    true_positives = data.get('true_positives', {})
    false_positives = data.get('false_positives', {})
    hunts = data.get('hunts', [])
    
    # Get analyzer to retrieve message subjects we may need
    try:
        analyzer = HuntAnalyzer(session['api_token'])
        results = analyzer.get_hunt_results(hunt_id)
        message_map = {msg['id']: analyzer.get_subject_from_message_group(msg) for msg in results}
    except Exception as e:
        logger.error(f"Error retrieving hunt results for mass categorization: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error retrieving hunt details: {str(e)}'})
    
    # Process each message ID
    successful_ids = []
    failed_ids = []
    
    for msg_id in message_ids:
        try:
            # Get subject from the map or use a default
            subject = message_map.get(msg_id, "Unknown subject")
            
            # Check existing categorization status
            was_tp = msg_id in true_positives
            was_fp = msg_id in false_positives
            
            # Remove from opposite category if needed
            if category == 'true_positive' and msg_id in false_positives:
                del false_positives[msg_id]
            elif category == 'false_positive' and msg_id in true_positives:
                del true_positives[msg_id]
            
            # Add to the correct category
            if category == 'true_positive':
                true_positives[msg_id] = {'hunt_id': hunt_id, 'subject': subject}
            else:
                false_positives[msg_id] = {'hunt_id': hunt_id, 'subject': subject}
                
            successful_ids.append(msg_id)
        except Exception as e:
            logger.error(f"Error categorizing message {msg_id}: {str(e)}")
            failed_ids.append(msg_id)
    
    # Update hunt stats
    for hunt in hunts:
        if hunt['id'] == hunt_id:
            # Recount for this hunt
            tp_count = sum(1 for tp in true_positives.values() if tp['hunt_id'] == hunt_id)
            fp_count = sum(1 for fp in false_positives.values() if fp['hunt_id'] == hunt_id)
            hunt['true_positives_count'] = tp_count
            hunt['false_positives_count'] = fp_count
            logger.info(f"Updated hunt {hunt_id} stats: TP={tp_count}, FP={fp_count}")
            break
    
    # Save data
    data['true_positives'] = true_positives
    data['false_positives'] = false_positives
    data['hunts'] = hunts
    save_data(data)
    
    logger.info(f"Mass categorization complete. {len(successful_ids)} succeeded, {len(failed_ids)} failed")
    return jsonify({
        'status': 'success', 
        'message': f'Successfully categorized {len(successful_ids)} messages',
        'successful_count': len(successful_ids),
        'failed_count': len(failed_ids)
    })

@app.route('/compare')
def compare():
    """Compare hunts page."""
    if 'api_token' not in session:
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    data = load_data()
    return render_template('compare.html', hunts=data.get('hunts', []))

@app.route('/compare_hunts', methods=['POST'])
def compare_hunts():
    """Compare two hunts and show results."""
    logger.info("Starting hunt comparison")
    
    if 'api_token' not in session:
        logger.warning("API token not set, redirecting to index")
        flash('Please set your API token first', 'warning')
        return redirect(url_for('index'))
    
    previous_hunt_id = request.form.get('previous_hunt')
    current_hunt_id = request.form.get('current_hunt')
    logger.info(f"Comparing hunts: previous={previous_hunt_id}, current={current_hunt_id}")
    
    if not previous_hunt_id or not current_hunt_id:
        logger.warning("Missing hunt IDs for comparison")
        flash('Please select both hunts for comparison', 'danger')
        return redirect(url_for('compare'))
    
    if previous_hunt_id == current_hunt_id:
        logger.warning("Same hunt selected for comparison")
        flash('Please select different hunts for comparison', 'danger')
        return redirect(url_for('compare'))
    
    # Load data
    data = load_data()
    hunts = data.get('hunts', [])
    
    # Find the hunts
    prev_hunt = next((h for h in hunts if h['id'] == previous_hunt_id), None)
    curr_hunt = next((h for h in hunts if h['id'] == current_hunt_id), None)
    
    if not prev_hunt or not curr_hunt:
        logger.warning(f"Hunt not found: prev={prev_hunt is None}, curr={curr_hunt is None}")
        flash('Hunt not found', 'danger')
        return redirect(url_for('compare'))
    
    # Check if all samples in both hunts have been categorized
    prev_total = prev_hunt.get('total_samples', 0)
    prev_tp_count = prev_hunt.get('true_positives_count', 0)
    prev_fp_count = prev_hunt.get('false_positives_count', 0)
    prev_pre_labeled = prev_hunt.get('pre_labeled_count', 0)
    prev_categorized = prev_tp_count + prev_fp_count
    prev_total_categorized = prev_categorized
    
    # Account for pre-labeled samples only if they're not already counted in tp/fp counts
    if prev_pre_labeled > 0 and prev_categorized < prev_total:
        prev_total_categorized = min(prev_total, prev_categorized + prev_pre_labeled)
    
    curr_total = curr_hunt.get('total_samples', 0)
    curr_tp_count = curr_hunt.get('true_positives_count', 0)
    curr_fp_count = curr_hunt.get('false_positives_count', 0)
    curr_pre_labeled = curr_hunt.get('pre_labeled_count', 0)
    curr_categorized = curr_tp_count + curr_fp_count
    curr_total_categorized = curr_categorized
    
    # Account for pre-labeled samples only if they're not already counted in tp/fp counts
    if curr_pre_labeled > 0 and curr_categorized < curr_total:
        curr_total_categorized = min(curr_total, curr_categorized + curr_pre_labeled)
    
    logger.info(f"Previous hunt: {prev_hunt['name']} - {prev_total_categorized}/{prev_total} categorized (including {prev_pre_labeled} pre-labeled)")
    logger.info(f"Current hunt: {curr_hunt['name']} - {curr_total_categorized}/{curr_total} categorized (including {curr_pre_labeled} pre-labeled)")
    
    # Log detailed stats for debugging
    logger.debug(f"Previous hunt stats: {prev_hunt}")
    logger.debug(f"Current hunt stats: {curr_hunt}")
    
    if prev_total_categorized < prev_total:
        logger.warning(f"Previous hunt not fully categorized: {prev_total_categorized}/{prev_total}")
        flash(f'Please categorize all samples in "{prev_hunt["name"]}" before comparing', 'warning')
        return redirect(url_for('analyze_hunt', hunt_id=previous_hunt_id))
    
    if curr_total_categorized < curr_total:
        logger.warning(f"Current hunt not fully categorized: {curr_total_categorized}/{curr_total}")
        flash(f'Cannot compare: "{curr_hunt["name"]} ({curr_total} samples, {curr_total_categorized}/{curr_total} labeled) - Incomplete" is not fully labeled. Please label all samples first.', 'warning')
        return redirect(url_for('analyze_hunt', hunt_id=current_hunt_id))
    
    # Load data
    data = load_data()
    hunts = data.get('hunts', [])
    true_positives = data.get('true_positives', {})
    false_positives = data.get('false_positives', {})
    
    # Get hunt information
    prev_hunt = next((h for h in hunts if h['id'] == previous_hunt_id), None)
    curr_hunt = next((h for h in hunts if h['id'] == current_hunt_id), None)
    
    if not prev_hunt or not curr_hunt:
        flash('Hunt not found', 'danger')
        return redirect(url_for('compare'))
    
    try:
        analyzer = HuntAnalyzer(session['api_token'])
        previous_results = analyzer.get_hunt_results(previous_hunt_id)
        current_results = analyzer.get_hunt_results(current_hunt_id)
        
        # Check if timeframes are similar
        timeframe_warning = None
        if 'timeframe' in prev_hunt and 'timeframe' in curr_hunt:
            prev_timeframe = prev_hunt['timeframe']
            curr_timeframe = curr_hunt['timeframe']
            
            # Check for significant timeframe differences
            try:
                prev_start = datetime.fromisoformat(prev_timeframe['start_time'].replace('Z', '+00:00'))
                prev_end = datetime.fromisoformat(prev_timeframe['end_time'].replace('Z', '+00:00'))
                curr_start = datetime.fromisoformat(curr_timeframe['start_time'].replace('Z', '+00:00'))
                curr_end = datetime.fromisoformat(curr_timeframe['end_time'].replace('Z', '+00:00'))
                
                # Check for overlapping timeframes
                if prev_end < curr_start or curr_end < prev_start:
                    timeframe_warning = "WARNING: Hunts have non-overlapping time ranges!"
                else:
                    # Check if duration is significantly different
                    prev_duration = prev_timeframe['duration_minutes']
                    curr_duration = curr_timeframe['duration_minutes']
                    
                    if abs(prev_duration - curr_duration) > 30:  # More than 30 minutes difference
                        timeframe_warning = f"WARNING: Hunt durations differ by {abs(prev_duration - curr_duration)} minutes"
                    
                    # Check for significant start time differences
                    start_diff_minutes = abs((prev_start - curr_start).total_seconds() / 60)
                    if start_diff_minutes > 30:  # More than 30 minutes difference
                        timeframe_warning = f"WARNING: Hunt start times differ by {int(start_diff_minutes)} minutes"
            except Exception:
                # If we can't parse the dates, don't show a warning
                pass
        
        # Collect all message IDs and subjects from both hunts
        prev_messages = {msg["id"]: analyzer.get_subject_from_message_group(msg) for msg in previous_results}
        curr_messages = {msg["id"]: analyzer.get_subject_from_message_group(msg) for msg in current_results}
        
        # Identify true positives and false positives in previous hunt
        prev_true_positives = set(msg_id for msg_id in prev_messages.keys() if msg_id in true_positives)
        prev_false_positives = set(msg_id for msg_id in prev_messages.keys() if msg_id in false_positives)
        
        # Common and new/missing samples
        common_true_positives = list(prev_true_positives.intersection(curr_messages.keys()))
        missing_true_positives = list(prev_true_positives - set(curr_messages.keys()))
        common_false_positives = list(prev_false_positives.intersection(curr_messages.keys()))
        eliminated_false_positives = list(prev_false_positives - set(curr_messages.keys()))
        
        # Determine all true positives from all previous hunts that should be in current hunt
        all_previous_true_positives = set(true_positives.keys())
        missing_all_true_positives = list(all_previous_true_positives - set(curr_messages.keys()))
        
        # Identify new true positives (in current hunt but not in previous hunt)
        # First identify all messages in current hunt that are labeled as true positives
        curr_true_positives = set(msg_id for msg_id in curr_messages.keys() if msg_id in true_positives)
        # Then exclude those that were already in the previous hunt
        new_true_positives = list(curr_true_positives - prev_true_positives)
        
        # Generate MQL diff if available
        prev_mql = prev_hunt.get('mql_source', '')
        curr_mql = curr_hunt.get('mql_source', '')
        mql_diff = create_html_diff(prev_mql, curr_mql)
        
        # Prepare comparison data for template
        comparison = {
            'prev_hunt': prev_hunt,
            'curr_hunt': curr_hunt,
            'prev_samples': len(previous_results),
            'curr_samples': len(current_results),
            'prev_true_positives': len(prev_true_positives),
            'prev_false_positives': len(prev_false_positives),
            'curr_true_positives': len(curr_true_positives),
            'timeframe_warning': timeframe_warning,
            'mql_diff': mql_diff,
            'common_true_positives': [
                {'id': msg_id, 'prev_subject': prev_messages[msg_id], 'curr_subject': curr_messages[msg_id]}
                for msg_id in common_true_positives
            ],
            'common_false_positives': [
                {'id': msg_id, 'prev_subject': prev_messages[msg_id], 'curr_subject': curr_messages[msg_id]}
                for msg_id in common_false_positives
            ],
            'eliminated_false_positives': [
                {'id': msg_id, 'subject': prev_messages[msg_id]}
                for msg_id in eliminated_false_positives
            ],
            'missing_true_positives': [
                {'id': msg_id, 'subject': prev_messages[msg_id]}
                for msg_id in missing_true_positives
            ],
            'new_true_positives': [
                {'id': msg_id, 'subject': curr_messages[msg_id]}
                for msg_id in new_true_positives
            ],
            'missing_all_true_positives': []
        }
        
        # Add missing true positives from all hunts
        for msg_id in missing_all_true_positives:
            if msg_id in true_positives:
                tp_data = true_positives[msg_id]
                orig_hunt_id = tp_data.get('hunt_id', 'Unknown')
                orig_hunt = next((h for h in hunts if h['id'] == orig_hunt_id), {'name': 'Unknown Hunt'})
                
                comparison['missing_all_true_positives'].append({
                    'id': msg_id,
                    'subject': tp_data.get('subject', 'Unknown subject'),
                    'hunt_name': orig_hunt['name']
                })
        
        # Calculate metrics
        fp_reduction_count = len(eliminated_false_positives)
        fp_reduction_percent = (fp_reduction_count / len(prev_false_positives) * 100) if prev_false_positives else 0
        tp_retention_percent = (len(common_true_positives) / len(prev_true_positives) * 100) if prev_true_positives else 0
        new_tp_count = len(new_true_positives)
        
        comparison['metrics'] = {
            'fp_reduction_count': fp_reduction_count,
            'fp_reduction_percent': fp_reduction_percent,
            'tp_retention_percent': tp_retention_percent,
            'new_tp_count': new_tp_count
        }
        
        # Analysis
        if len(missing_all_true_positives) == 0 and fp_reduction_count > 0:
            message = f'Rule improvement: Current rule detects all true positives and reduces false positives by {fp_reduction_percent:.1f}%.'
            if new_tp_count > 0:
                message += f' Additionally, it found {new_tp_count} new true positives.'
            comparison['analysis'] = {
                'type': 'success',
                'message': message
            }
        elif len(missing_all_true_positives) > 0 and fp_reduction_count > 0:
            message = f'Mixed results: Current rule reduces false positives by {fp_reduction_percent:.1f}% but misses {len(missing_all_true_positives)} true positives.'
            if new_tp_count > 0:
                message += f' However, it found {new_tp_count} new true positives.'
            comparison['analysis'] = {
                'type': 'warning',
                'message': message
            }
        elif len(missing_all_true_positives) == 0 and fp_reduction_count == 0:
            message = f'Mixed results: Current rule maintains all true positives but did not reduce false positives.'
            if new_tp_count > 0:
                message += f' However, it found {new_tp_count} new true positives, which is positive.'
                comparison['analysis'] = {
                    'type': 'success',
                    'message': message
                }
            else:
                comparison['analysis'] = {
                    'type': 'warning',
                    'message': message
                }
        else:
            message = f'Possible regression: Current rule misses {len(missing_all_true_positives)} true positives and didn\'t reduce false positives.'
            if new_tp_count > 0:
                message += f' It did find {new_tp_count} new true positives, but the overall change appears negative.'
            comparison['analysis'] = {
                'type': 'danger',
                'message': message
            }
        
        return render_template('comparison_results.html', comparison=comparison)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('compare'))

if __name__ == '__main__':
    app.run(debug=True)