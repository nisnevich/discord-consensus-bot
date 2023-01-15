import unittest

# discover all test methods under the "tests" directory
for test_class in unittest.defaultTestLoader.discover("tests"):
    for test in test_class:
        result = unittest.TextTestRunner(verbosity=2).run(test)
