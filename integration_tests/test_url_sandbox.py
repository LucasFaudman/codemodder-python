from codemodder.codemods.url_sandbox import UrlSandbox
from integration_tests.base_test import BaseIntegrationTest


class TestUrlSandbox(BaseIntegrationTest):
    codemod = UrlSandbox
    code_path = "tests/samples/make_request.py"
    original_code = 'import requests\n\nrequests.get("www.google.com")\nvar = "hello"\n'
    expected_new_code = 'from security import safe_requests\n\nsafe_requests.get("www.google.com")\nvar = "hello"\n'
    expected_diff = '--- \n+++ \n@@ -1,4 +1,4 @@\n-import requests\n+from security import safe_requests\n \n-requests.get("www.google.com")\n+safe_requests.get("www.google.com")\n var = "hello"\n'
    expected_line_change = "3"
    change_description = UrlSandbox.CHANGE_DESCRIPTION
