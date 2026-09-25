{
    "name": "Demo Library",
    "summary": "Minimal book-lending module used to demo the project workflow",
    "version": "19.0.1.0.0",
    "category": "Services",
    "author": "Softspaceg",
    "website": "https://github.com/ahmedelkady111/odoo-workflow-demo",
    "license": "LGPL-3",
    "depends": ["base"],
    # Load order matters: security -> data -> views -> menus.
    # Getting this wrong works on upgrade and fails on a clean install.
    "data": [
        "security/ir.model.access.csv",
        "data/demo_library_data.xml",
        "views/library_book_views.xml",
        "views/demo_library_menus.xml",
    ],
    "installable": True,
}
