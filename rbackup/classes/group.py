import logging
import typing

if typing.TYPE_CHECKING:
    from .config import Config
from .job import Job


class Group:
    """ Gets instantiated by Config.\n
    Attrs:
        name: str           - Group name
        jobs: list[Job]     - List of jobs
        skipOnFail: bool    - Skip subsequent jobs if one fails with an error
    """

    def __init__(self, group: dict, config: 'Config' = None):
        """ Do not instantiate directly, use Config.get()
        """
        self.name       = group['name'].strip() if 'name' in group else ''
        self.logger     = logging.getLogger(f"GROUP {self.name}")
        self.skipOnFail = group['skipOnFail'] if 'skipOnFail' in group else False

        self.jobs = []
        self.logger.debug("Finding jobs...")
        for job in group.get('jobs') or []:
            self.jobs.append(Job(job))

    @classmethod
    def filter_groups(cls, groups: list, included: list = None, excluded: list = None):
        """ Returns an iterable of matching groups.  Do not use both included
        and excluded params together.

        :param groups: (list) the unfiltered list of job groups
        :param included: (list) group names to include (exclude all others)
        :param excluded: (list) group names to exclude (include all others)

        :returns (Generator): an iterable of matching groups
        """
        if included:
            for group in groups:
                if group.name in included:
                    yield group
        elif excluded:
            for group in groups:
                if group.name not in excluded:
                    yield group
        else:
            for group in groups:
                yield group
