"""Synthetic records for the public preview."""

DEMO_CATEGORIES = (
    {'pk': 1, 'name': 'Personal', 'entry_count': 2},
    {'pk': 2, 'name': 'Work', 'entry_count': 1},
)

DEMO_ENTRIES = {
    1: {'pk': 1, 'website': 'mail.example', 'username': 'alex@example.test',
        'category': DEMO_CATEGORIES[0], 'category_id': 1, 'password': 'Sample-Mail-47!'},
    2: {'pk': 2, 'website': 'photos.example', 'username': 'alex.photos',
        'category': DEMO_CATEGORIES[0], 'category_id': 1, 'password': 'Sample-Photos-82!'},
    3: {'pk': 3, 'website': 'workspace.example', 'username': 'alex.work',
        'category': DEMO_CATEGORIES[1], 'category_id': 2, 'password': 'Sample-Workspace-65!'},
}
