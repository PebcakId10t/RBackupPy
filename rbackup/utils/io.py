import sys

def eprint(*args, **kwargs):
    """Helper for printing to stderr"""
    print(*args, file=sys.stderr, **kwargs)


def prompt_yes_or_no(question: str, default='y') -> bool:
    """Prompts user with a yes/no question until a choice is made and then 
    returns boolean True/False indicating yes/no.
    """
    affirmatives = {'yes', 'y'}
    negatives = {'no', 'n'}
    if default not in affirmatives and default not in negatives:
        raise ValueError("Bad default - y(es)/n(o) only")
    eprint(question, end=(' [Y/n]: ' if default in affirmatives else ' [y/N]: '))
    while True:
        choice = input().lower()
        if choice in affirmatives:
            return True
        elif choice in negatives:
            return False
        elif not choice:
            if default in affirmatives:
                return True
            else:
                return False
        else:
            eprint("Please answer yes or no.")
