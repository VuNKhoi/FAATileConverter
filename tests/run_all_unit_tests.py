import os
import sys
import unittest

# Ensure project root is in sys.path for 'scripts' imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class EmojiTestResult(unittest.TextTestResult):
    def addSuccess(self, test):
        super().addSuccess(test)
        self.stream.write(f"\033[92m✓\033[0m {test}\n")
        self.stream.flush()
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.write(f"\033[91mx\033[0m {test}\n")
        self.stream.flush()
    def addError(self, test, err):
        super().addError(test, err)
        self.stream.write(f"\033[91mx\033[0m {test}\n")
        self.stream.flush()

def main():
    loader = unittest.TestLoader()
    suite = loader.discover('tests')
    runner = unittest.TextTestRunner(verbosity=0, resultclass=EmojiTestResult)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    main()
