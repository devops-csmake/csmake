# <copyright>
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
class AspectFlowControl:

    #Policies on conflicted votes
    MAJORITY='votes' #50% + 1 wins
    OVERRIDE='override' #Demands win
    DEFAULT='default'  #Default wins (dictated by main concern, default)

    def initFlowControlIssue(
        self, name, doc=None, default=False, policy='default'):
        if name not in self.issues:
            initstate = { 
                'default' : default, 
                'policy' : policy, 
                '__doc__' : doc }
        else:
            initstate = self.issues[name]['initstate']
        self.issues[name] = {
            'votes' : [],
            'voters' : [],
            'override' : False,
            'overrider' : None,
            'initstate' : initstate }
        self.issues[name].update(initstate)

    def resetFlowControlIssue(self, name, doc, default, policy ):
        del self.issues[name]
        self.initFlowControlIssue(name, doc, default, policy)

    def __init__(self, log):
        self.issues = {}
        self.log = log
        self.initFlowControlIssue(
            'doNotStart',
            "Tells main concern to not start a build step")
        self.initFlowControlIssue(
            'tryAgain',
            "Tells main concern to execute again")
        self.initFlowControlIssue(
            'doNotAvoid',
            "Tells main concern to execute even against build avoidance advice")

    def _dumpPointsToInfo(self):
        for key, value in self.issues.items():
            self.log.info("Advise: %s", key)
            self.log.info("    %s", value['__doc__'])

    def _verifyIssue(self, issue):
        if issue not in self.issues:
            self.log.error("Advise '%s' is not available", issue)
            self.log.info("---Current Advise Points---")
            self._dumpPointsToInfo()
            raise AttributeError(issue)

    def vote(self, issue, vote, voter):
        self._verifyIssue(issue)
        self.issues[issue]['votes'].append( vote )
        self.issues[issue]['voters'].append( voter )

    def setPolicy(self, issue, policy):
        self._verifyIssue(issue)
        self.issues[issue]['policy'] = policy

    def override(self, issue, vote, voter):
        self._verifyIssue(issue)
        self.log.devdebug("Overriding %s, Vote %s, Voter %s",
            issue,
            str(vote),
            str(voter) )
        advise = self.issues[issue]
        oldOverrider = advise['overrider']
        self.log.devdebug("Old overrider is: %d", oldOverrider)
        assert advise['overrider'] is None or oldOverrider == voter

        advise['overrider'] = voter
        advise['override'] = vote
        advise['policy'] = AspectFlowControl.OVERRIDE

    def query(self, issue):
        self._verifyIssue(issue)
        advice = self.issues[issue]
        votes = advice['votes']

        self.log.devdebug("Voting (%s) is: %s", issue, str(votes))
        if len(votes) == 0:
            if advice['policy'] == AspectFlowControl.MAJORITY:
                return advice['default']
            return advice[advice['policy']]
        if len(votes) == votes.count(votes[0]):
            self.log.devdebug("Unanimous: %s", str(votes[0]))
            return votes[0]
        elif advice['policy'] == AspectFlowControl.MAJORITY:
            result = votes.count(True) > votes.count(False)
            self.log.devdebug("Majority: %s", str(result))
            return result
        else:
            self.log.devdebug(
                "Policy: %s, Vote: %s", 
                advice['policy'],
                advice[advice['policy']] )
            return advice[advice['policy']]

    def advice(self, issue):
        result = self.query(issue)
        self.initFlowControlIssue(issue)
        return result
