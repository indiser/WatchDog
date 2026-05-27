import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from functools import wraps


load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local_test.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Schema
class TargetURL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    interval_minutes = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, default=True)
    last_pinged_at = db.Column(db.DateTime, default=None)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    admin_user = os.environ.get('ADMIN_USER')
    admin_pass = os.environ.get('ADMIN_PASS')
    return username == admin_user and password == admin_pass

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Unauthorized. Access is restricted to the administrator.', 401,
    {'WWW-Authenticate': 'Basic realm="WatchDog Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# Helper: compute stats for the stats bar
# ─────────────────────────────────────────────
def _get_stats_context():
    """Return template context dict with target counts."""
    all_targets = TargetURL.query.all()
    active_count = sum(1 for t in all_targets if t.is_active)
    paused_count = len(all_targets) - active_count
    return {
        'total_targets': len(all_targets),
        'active_count': active_count,
        'paused_count': paused_count,
    }

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route('/')
@requires_auth
def dashboard():
    """Renders the visual interface."""
    all_targets = TargetURL.query.all()
    stats = _get_stats_context()
    return render_template('index.html', targets=all_targets, **stats)


@app.route('/add_target_ui', methods=['POST'])
@requires_auth
def add_target_ui():
    """Handles form submissions from the web browser."""
    url = request.form.get('url')
    interval = request.form.get('interval_minutes', 5)
    
    if url:
        new_target = TargetURL(url=url, interval_minutes=int(interval))
        db.session.add(new_target)
        db.session.commit()
        
    # Redirect back to the dashboard so the user sees the updated table
    return redirect(url_for('dashboard'))


@app.route('/targets_partial')
@requires_auth
def targets_partial():
    """Returns just the table body HTML for HTMX polling."""
    all_targets = TargetURL.query.all()
    return render_template('_targets_table_body.html', targets=all_targets)


@app.route('/targets_partial_mobile')
@requires_auth
def targets_partial_mobile():
    """Returns mobile card list HTML for HTMX polling."""
    all_targets = TargetURL.query.all()
    return render_template('_targets_mobile_body.html', targets=all_targets)


@app.route('/stats')
@requires_auth
def stats():
    """Returns the stats bar HTML for HTMX polling."""
    ctx = _get_stats_context()
    return render_template('_stats_bar.html', **ctx)


@app.route('/delete_target/<int:target_id>', methods=['DELETE'])
@requires_auth
def delete_target(target_id):
    """Deletes a target. Returns empty string so HTMX removes the row."""
    target = TargetURL.query.get_or_404(target_id)
    db.session.delete(target)
    db.session.commit()
    return ''  # HTMX replaces the row with nothing → row disappears


@app.route('/toggle_target/<int:target_id>', methods=['PATCH'])
@requires_auth
def toggle_target(target_id):
    """Toggles a target's active/paused status. Returns the updated row partial."""
    target = TargetURL.query.get_or_404(target_id)
    target.is_active = not target.is_active
    db.session.commit()
    return render_template('_target_row.html', target=target)
    

if __name__ == '__main__':
    app.run(debug=True)
