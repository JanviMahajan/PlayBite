# Server-side gameplay validator service
# Expose a simple validate function that enforces basic sanity checks.

def validate_gameplay(slug, score, time_taken, game_duration_seconds):
    """Return (ok:bool, reason:str)"""
    # Define maximums per game to prevent inflated scores
    max_allowed = {
        'memory-match': 10000,
        'maze-escape': 5000,
        'fruit-slice': 8000,
    }
    max_score = max_allowed.get(slug, 10000)

    # Basic checks
    if score < 0:
        return False, 'negative_score'
    if score > max_score:
        return False, 'score_too_high'

    if time_taken < 0:
        return False, 'negative_time'
    if time_taken > (game_duration_seconds + 10):
        return False, 'time_too_long'

    # Passed basic checks
    return True, ''
