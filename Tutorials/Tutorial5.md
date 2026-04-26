Tutorial 5: Creating csmake Modules

In this tutorial you will learn:

    How to create a basic csmake module
    How to use logging in csmake
    How to implement phases in modules to work together
    How to write documentation for a csmake module
    How to refer to other modules in a module implementation

This tutorial requires a 64-bit Linux (amd64) debian-based distro operating system
Step 1: Ensure csmake is installed

This exercise uses csmake.  If you do not have version 1.3.2 or later of csmake, please install that now
Step 2: Create New Directories for the Tutorial
mkdir Tutorial5
cd Tutorial5
mkdir CsmakeModules
cd CsmakeModules

A local CsmakeModules directory is one of the places csmake will look for modules.  Having a local CsmakeModules directory allows you to create custom build modules, or override existing modules (although overriding is discouraged over subclassing or using aspects to accomplish your build).
Step 3: Create a simple csmake Module

In the CsmakeModules directory, create a file call TutorialBuildStep.py
TutorialBuildStep.py
from CsmakeCore.CsmakeModule import CsmakeModule
 
class TutorialBuildStep(CsmakeModule):
    """Library: Tutorial5
       Purpose: To learn how to build modules with csmake
       Phases:
           shop - Buy specified apples and bananas
           take_back - Return remaining apples and bananas for a refund
           consume - Eat apples and bananas (all of them)
       Options:
           apple - How many apples we want
           banana - How many bananas we want"""
 
    REQUIRED_OPTIONS = ['apple', 'banana']
 
    def shop(self, options):
        self.log.info("I'm shopping for %s bananas and %s apples", options['banana'], options['apple'])

As you can see, we've done a few things with this module already:

    We've created a class called TutorialBuildStep in a file called TutorialBuildStep.py  -  This is important to note because csmake only wants to load modules from the same name as the file name - this name is also the name you will use for the section type when you refer to the module in your csmakefile.
    We've created some simple documentation - there's nothing fancy here.  What you put in the class documentation string is what anyone that does "csmake --list-type=TutorialBuildStep" will see.
    Created a 'shop' method.  When we invoke csmake with a csmakefile that has a [TutorialBuildStep@whatever] section with the "shop" phase, this method will be invoked.
    We used the "self.log.info" method.  self.log is a "Csmake.Result" object, which handles things such as keeping track of the logging results and the pass/fail status of the module.
    We created a class variable called REQUIRED_OPTIONS, which the csmake module framework will refer to and use to check to see if the csmakefile has the options your module requires (and gives a nicer error message than, KeyError: apples, for example.  Use of REQUIRED_OPTIONS is optional (heh).

Let's go ahead and try using this module.

Create a csmakefile in your "Tutorial5" directory (not the CsmakeModules directory) that refers to the module like this:
[command@]
00=mymodule
 
[TutorialBuildStep@mymodule]
apple=5
banana=99

Now let's try out the module (from the Tutorial5 directory):
$ csmake shop
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
` WARNING  : Phase 'shop' not delcared in ~~phases~~ section
` WARNING  :   Run: csmake --list-type=~~phases~~ for help
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  Begin
------------------------------------------------------------------
------------------------------------------------------------------
                           Step: Executing                         
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
command@: ERROR    : Step 'mymodule' FAILED
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
+ command@      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
` WARNING  : Phase 'shop' not delcared in ~~phases~~ section
` WARNING  :   Run: csmake --list-type=~~phases~~ for help
   SEQUENCE EXECUTED: shop
` ERROR    : csmake exited with code 1
------------------------------------------------------------------
  __   __   __   __   __   __   __   __   __   __   __   __   __   __   __
 _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_
 \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/
     csmake: Failed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

Well...that didn't go quite as expected! ('declared' isn't even spelled right in csmake's output....oops!)

We're complaining about ~~phases~~, we don't see our output, the execution failed, geesh!

First of all, we didn't see our output, because we used "self.log.info", info is only output if we ask csmake to give us "--verbose" or "--debug" output.  So, let's try that now and at least feel like we accomplished something!
$ csmake --verbose shop
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
` WARNING  : Phase 'shop' not delcared in ~~phases~~ section
` WARNING  :   Run: csmake --list-type=~~phases~~ for help
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  Begin
------------------------------------------------------------------
TutorialBuildStep@mymodule: INFO     : I'm shopping for 99 bananas and 5 apples
------------------------------------------------------------------
                           Step: Executing                         
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
command@: ERROR    : Step 'mymodule' FAILED
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
+ command@      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
` WARNING  : Phase 'shop' not delcared in ~~phases~~ section
` WARNING  :   Run: csmake --list-type=~~phases~~ for help
   SEQUENCE EXECUTED: shop
` ERROR    : csmake exited with code 1
------------------------------------------------------------------
  __   __   __   __   __   __   __   __   __   __   __   __   __   __   __
 _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_
 \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/
     csmake: Failed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

And there it is: "TutorialBuildStep@mymodule: INFO : I'm shopping for 99 bananas and 5 apples"
Step 4: Adding ~~phases~~ to your csmakefile

OK, let's go back and fix the rest, let's add a ~~phases~~ section to our csmakefile to get csmake a little happier and document what the heck someone's supposed to do if they stumble across your project

Open your csmakefile in an editor and add the following section (I prefer the top, but anywhere will do)
[~~phases~~]
shop=Purchase items for each defined step
take_back=Return all the items for each defined step
consume=Eat the items from each step
work=Earn more resources to make shopping successful

OK, let's leave it at that for now - with at least our phases defined we can do a phase without csmake complaining it didn't know about that phase!
Step 5: Adding "passed" to your module's method

The reason the above build is failing is because our module doesn't provide any status.  If csmake doesn't get any status from a module, you'll see that "Step: Executing" status and csmake will assume something went wrong and fail the build.  So, let's fix that up.

Open your CsmakeModules/TutorialBuildStep.py in an editor

Let's change 'shop' to look like this:
def shop(self, options):
    self.log.info("I'm shopping for %s bananas and %s apples", options['banana'], options['apple'])
    self.log.passed()

With Step 4 and Step 5's fixes, we should be able to see a much better result.  Let's give execution a try again (Reminder: from the Tutorial5 directory)
$ csmake --verbose shop
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
             Purchase items for each defined step
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  Begin
------------------------------------------------------------------
TutorialBuildStep@mymodule: INFO     : I'm shopping for 5 bananas and 99 apples
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ TutorialBuildStep@mymodule      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
             Purchase items for each defined step
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: shop
     Purchase items for each defined step
------------------------------------------------------------------
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
     csmake: Passed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

Allright!  That's much better!  It passed the build and it even tells us what the phases are supposed to be for.
Step 6: Making the Module Functional

By now, we've seen how to fill out some of the basics to execute our module, let's make it actually do something - and while we're at it, let's give it a better name.
Making our Module More Descriptive: ManageProduce

Let's start by giving our module a better name.  When we change the name, we need to change both the name of the file and the name of the class. 

A name like, ManageProduce would be a lot more descriptive.  Let's start with the name of the file:
#Assuming we're starting in the Tutorial5 directory
cd CsmakeModules
mv TutorialBuildStep.py ManageProduce.py

Now, we need to fix the name of the class - open ManageProduce.py in your editor and change the name of the class to ManageProduce.

The top of your file should now look like this:
from CsmakeCore.CsmakeModule import CsmakeModule
 
class ManageProduce(CsmakeModule):

One more thing we need to fix, the csmakefile, which is back up a directory in the Tutorial5 directory.

Open csmakefile in your editor and fix up the section, let's give the section a better id as well:
csmakefile
[~~phases~~]
shop=Purchase items for each defined step
take_back=Return all the items for each defined step
consume=Eat the items from each step
work=Earn more resources to make shopping successful
 
[command@]
00=produce
 
[ManageProduce@produce]
apple=5
banana=99
Implementing the 'ManageProduce' Module

Let's go back to the CsmakeModules directory and edit our "ManageProduce.py" module.

We have a couple more sections to fill out.  In order for this example to make sense, we need to maintain some state.  To make it easy, let's use a dictionary and pickle it into a file.  The state we should probably track is how many apples, bananas and money we have.  So, let's implement our other phases, pickling and produce tracking now.

Open the "ManageProduce.py" in your editor and change it to look like this:
ManageProduce.py
from CsmakeCore.CsmakeModule import CsmakeModule
import pickle
 
class ManageProduce(CsmakeModule):
    """Library: Tutorial5
       Purpose: To learn how to build modules with csmake
       Phases:
           shop - Buy specified apples and bananas
           take_back - Return remaining apples and bananas for a refund
           consume - Eat apples and bananas
       Options:
           apple - How many apples we want
           banana - How many bananas we want"""
 
    REQUIRED_OPTIONS = ['apple', 'banana']
 
    BananasCost=1
    ApplesCost=2
 
    @staticmethod
    def _readState():
        try:
            with open('produce.pickle') as pickleFile:
                return pickle.load(pickleFile)
        except:
            return { 'apples' : 0, 'bananas' : 0, 'wallet': 0 }
 
    @staticmethod
    def _writeState(produce):
        with open("produce.pickle", 'w') as pickleFile:
            pickle.dump(produce, pickleFile)
 
    def shop(self, options):
        produce = self._readState()
        self.log.info("I'm shopping for %s bananas and %s apples", options['banana'], options['apple'])
        cartTotal = self.BananasCost * int(options['banana'])
        cartTotal = cartTotal + self.ApplesCost * int(options['apple'])
        if cartTotal > produce['wallet']:
            self.log.error("You don't have enough money")
            self.log.error("   Cart Total:  $%d", cartTotal)
            self.log.error("   Your Wallet: $%d", produce['wallet'])
            self.log.failed()
            return False
         
        #Purchase the produce
        produce['wallet'] = produce['wallet'] - cartTotal
        produce['apples'] = produce['apples'] + int(options['apple'])
        produce['bananas'] = produce['bananas'] + int(options['banana'])
        #Save the new state
        self._writeState(produce)
        self.log.passed()
        return True
 
    def take_back(self, options):
        produce = self._readState()
        returnedAmount = 0
        #Take care of the bananas
        if int(options['banana']) > produce['bananas'] \
           and produce['bananas'] > 0:
            self.log.warning("You are trying to return %s bananas, but you only have %d", options['banana'], produce['bananas'])
            self.log.warning("You will return the remainder of the bananas")
            returnedAmount = returnedAmount + produce['bananas'] * self.BananasCost
            produce['bananas'] = 0
        elif produce['bananas'] <= 0:
            self.log.error("Yes...you have no bananas")
            self.log.failed()
            return False
        else:
            self.log.info("You are returning %s bananas", option['banana'])
            produce['bananas'] = produce['bananas'] - option['banana']
            returnedAmount = returnedAmount + option['banana'] * self.BananasCost
        #Take care of the apples
        if int(options['apple']) > produce['apples'] \
           and produce['apples'] > 0:
            self.log.warning("You are trying to return %s apples, but you only have %d", options['apple'], produce['apples'])
            self.log.warning("You will return the remainder of the apples")
            returnedAmount = returnedAmount + produce['apples'] * self.BananasCost
            produce['apples'] = 0
        elif produce['apples'] <= 0:
            self.log.error("Yes...you have no apples")
            self.log.failed()
            return False
        else:
            self.log.info("You are returning %s apples", option['apple'])
            produce['apples'] = produce['apples'] - option['apple']
            returnedAmount = returnedAmount + option['apple'] * self.BananasCost
        self.log.info("You will be getting back $%d" % returnedAmount)
        produce['wallet'] = produce['wallet'] + returnedAmount
        self.log.info("You now have $%d in your wallet", produce['wallet'])
        self.log.debug("produce == %s", str(produce))
        self._writeState(produce)
        self.log.passed()
        return True
 
    def consume(self, options):
        produce = self._readState()
        #Take care of the bananas
        if int(options['banana']) > produce['bananas'] \
           and produce['bananas'] > 0:
            self.log.warning("You are trying to eat %s bananas, but you only have %d", options['banana'], produce['bananas'])
            self.log.warning("You will eat the remainder of the bananas")
            produce['bananas'] = 0
        elif produce['bananas'] <= 0:
            self.log.error("Yes...you have no bananas")
            self.log.failed()
            return False
        else:
            self.log.info("You are eating %s bananas", option['banana'])
            produce['bananas'] = produce['bananas'] - option['banana']
        #Take care of the apples
        if int(options['apple']) > produce['apples'] \
           and produce['apples'] > 0:
            self.log.warning("You are trying to eat %s apples, but you only have %d", options['apple'], produce['apples'])
            self.log.warning("You will eat the remainder of the apples")
            produce['apples'] = 0
        elif produce['apples'] <= 0:
            self.log.error("Yes...you have no apples")
            self.log.failed()
            return False
        else:
            self.log.info("You are eating %s apples", option['apple'])
            produce['apples'] = produce['apples'] - option['apple']
            returnedAmount = returnedAmount + option['apple'] * self.BananasCost
        self.log.debug("produce == %s", str(produce))
        self._writeState(produce)
        self.log.passed()
        return True

Now, obviously, if you run this, you have no money in your wallet, so this will fail.

As you can see, the biggest thing we've added other than the algorithm to manage buying and taking back apples and bananas is the prompts to the user.  There are "error", "warning", "info", and "debug" logging statements.  A Result object (what self.log is here) can also handle, "devdebug" which is output if csmake gets a --dev-output flag, and "critical" if there's a serious problem, this is really for internal use, but may be used in rare circumstances when the build finds itself completely in an unexpected context, for example.

The rest of the changes should be fairly obvious.  We've added a self.log.failed() for some cases and we've also added return values.

The return values aren't really used here - return values are mostly helpful if your module invokes other modules and wants to get and use the results.

A module phase implementation's return results are stored by phase in the module's Result object.

Let's go ahead and try to buy some apples and bananas:
$ csmake --verbose shop
 
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
             Purchase items for each defined step
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
ManageProduce@produce: INFO     : I'm shopping for 99 bananas and 5 apples
ManageProduce@produce: ERROR    : You don't have enough money
ManageProduce@produce: ERROR    :    Cart Total:  $109
ManageProduce@produce: ERROR    :    Your Wallet: $0
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
command@: ERROR    : Step 'produce' FAILED
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
+ command@      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
             Purchase items for each defined step
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: shop
     Purchase items for each defined step
` ERROR    : csmake exited with code 1
------------------------------------------------------------------
  __   __   __   __   __   __   __   __   __   __   __   __   __   __   __
 _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_
 \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/
     csmake: Failed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
Implementing a 'WorkAndGetPaid' Module

Obviously, what we have right now is insufficient, unless we hack money into our wallet (smile)  Let's be honest and make some money by creating a module that will stand for work worthy of getting paid.

In our Tutorial5/CsmakeModules' directory, let's go ahead and open an editor to edit a new file called 'WorkAndGetPaid':
WorkAndGetPaid.py
from CsmakeCore.CsmakeModule import CsmakeModule
from CsmakeModules.ManageProduce import ManageProduce
 
class WorkAndGetPaid(CsmakeModule):
    """Library: Tutorial5
       Purpose: To execute tracking work and payment
       Phases:
           work - Work and get paid - simple enough
       Options:
           wages - amount paid per period in dollars"""
 
    REQUIRED_IPTIONS = ['wages']
 
    def work(self, options):
        #Here we're going to use our ManageProduce static methods
        produce = ManageProduce._readState()
        wages = int(options['wages'])
        self.log.info("You worked, now you get paid $%d", wages)
        produce['wallet'] = produce['wallet'] + wages
        self.log.info("You now have $%d in your wallet", produce['wallet'])
        self.log.debug("Produce state: %s", str(produce))
        self.log.passed()
        ManageProduce._writeState(produce)
        return True

Notice, we reused the static methods defined in the "ManageProduce" module.  Notice also, that we used "from CsmakeModules.ManageProduce", this clues csmake in that we're using another module.  Any csmake module that csmake can access can be accessed in this way in other modules' implementations.

Let's go ahead and make a couple of changes to our csmakefile mow that we have a way to get paid.  To utilize the idea that we can use a single module for multiple sections, we'll have a "good-week" and a "bad-week" section.  We'll also implement a couple of commands to help us with this, and we'll document our commands, so that when we do (and we'll try this in a minute), "csmake --list-commands" we'll get useful information.

From the "Tutorial5" directory, open csmakefile in your editor and change it to look like this:
csmakefile
[~~phases~~]
shop=Purchase items for each defined step
return=Return all the items for each defined step
consume=Eat the items from each step
work=Earn more resources to make shopping successful
 
[command@]
description="By default - we shop"
00=produce
 
[ManageProduce@produce]
apple=5
banana=99
 
[WorkAndGetPaid@good-week]
wages=200
 
[WorkAndGetPaid@bad-week]
wages=100
 
[command@good]
description="This represents a good week"
00=good-week, produce
 
[command@bad]
description="This represents a bad week"
00=bad-week, produce

We now have three different commands, "blank" (i.e. '') which is our default command, and a 'good' and 'bad' command.  The default command just does the shopping, while good and bad both have work and shopping together.

Since we have multiple commands, it's a good idea to add some documentation.

You can see what commands are defined in a csmakefile by asking csmake to list the commands like:
$ csmake --list-commands
 
================= Defined commands =================
    (default) - "By default - we shop"
    good - "This represents a good week"
    bad - "This represents a bad week"

OK, now let's just work this week, no shopping.  And, let's call it a "good" week  So, on the command line, we would do (we'll go ahead and ask for --verbose so we get all the information):
$ csmake --verbose --command=good work
 
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: work
             Earn more resources to make shopping successful
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@good      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  Begin
------------------------------------------------------------------
WorkAndGetPaid@good-week: INFO     : You worked, now you get paid $200
WorkAndGetPaid@good-week: INFO     : You now have $200 in your wallet
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
` WARNING  : Could not dispatch a 'work' or 'default' method for the section 'ManageProduce@produce'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(produce) Looking for method: work
------------------------------------------------------------------
 - - - - - - - - - - - -   Step: Skipped   - - - - - - - - - - - -
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@good      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: work
             Earn more resources to make shopping successful
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: work
     Earn more resources to make shopping successful
------------------------------------------------------------------
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
     csmake: Passed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

Swell, so now we have $200.  You'll notice that the entire command (all the id's in the command) was referenced, but "ManageProduce" doesn't deal with the 'work' phase, so it was skipped - with '--verbose' you get to see exactly what csmake was looking for from the module and couldn't find:
` WARNING  : Could not dispatch a 'work' or 'default' method for the section 'ManageProduce@produce'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(produce) Looking for method: work

To see this further, let's go ahead and shop, but let's use the "good" command again:
$ csmake --command=good --verbose shop
 
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
             Purchase items for each defined step
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@good      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  Begin
------------------------------------------------------------------
` WARNING  : Could not dispatch a 'shop' or 'default' method for the section 'WorkAndGetPaid@good-week'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(good-week) Looking for method: shop
------------------------------------------------------------------
 - - - - - - - - - - - -   Step: Skipped   - - - - - - - - - - - -
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
ManageProduce@produce: INFO     : I'm shopping for 99 bananas and 5 apples
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@good      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
             Purchase items for each defined step
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: shop
     Purchase items for each defined step
------------------------------------------------------------------
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
     csmake: Passed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

Now, if everything went right, I should be able to try to buy more and fail because I don't have enough money left (200-109 == 91 obviously < 109).
$ csmake --command=good --debug shop
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
             Purchase items for each defined step
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@good      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  Begin
------------------------------------------------------------------
` WARNING  : Could not dispatch a 'shop' or 'default' method for the section 'WorkAndGetPaid@good-week'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(good-week) Looking for method: shop
------------------------------------------------------------------
 - - - - - - - - - - - -   Step: Skipped   - - - - - - - - - - - -
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
ManageProduce@produce: INFO     : I'm shopping for 99 bananas and 5 apples
ManageProduce@produce: ERROR    : You don't have enough money
ManageProduce@produce: ERROR    :    Cart Total:  $109
ManageProduce@produce: ERROR    :    Your Wallet: $91
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
command@good: ERROR    : Step 'produce' FAILED
------------------------------------------------------------------
 .:*~*:._.:*~*:._.:*~*:.   Step: Failed   .:*~*:._.:*~*:._.:*~*:.
------------------------------------------------------------------
+ command@good      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
             Purchase items for each defined step
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: shop
     Purchase items for each defined step
` ERROR    : csmake exited with code 1
------------------------------------------------------------------
  __   __   __   __   __   __   __   __   __   __   __   __   __   __   __
 _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_ _\/_
 \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/ \/\/
     csmake: Failed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

So, sure enough, we didn't have enough money, so now let's work and then shop:
$ csmake --verbose --command=good work shop
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.3.2
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: work
             Earn more resources to make shopping successful
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@good      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  Begin
------------------------------------------------------------------
WorkAndGetPaid@good-week: INFO     : You worked, now you get paid $200
WorkAndGetPaid@good-week: INFO     : You now have $291 in your wallet
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
` WARNING  : Could not dispatch a 'work' or 'default' method for the section 'ManageProduce@produce'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(produce) Looking for method: work
------------------------------------------------------------------
 - - - - - - - - - - - -   Step: Skipped   - - - - - - - - - - - -
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@good      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: work
             Earn more resources to make shopping successful
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: shop
             Purchase items for each defined step
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@good      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  Begin
------------------------------------------------------------------
` WARNING  : Could not dispatch a 'shop' or 'default' method for the section 'WorkAndGetPaid@good-week'
` INFO     : Could not find an appropriate method to call
` INFO     : ---(good-week) Looking for method: shop
------------------------------------------------------------------
 - - - - - - - - - - - -   Step: Skipped   - - - - - - - - - - - -
------------------------------------------------------------------
++ WorkAndGetPaid@good-week      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ ManageProduce@produce      ---  Begin
------------------------------------------------------------------
ManageProduce@produce: INFO     : I'm shopping for 99 bananas and 5 apples
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ ManageProduce@produce      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@good      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: shop
             Purchase items for each defined step
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
` WARNING  : No sequences have been defined in ~~phases~~
` WARNING  :   Run: csmake --list-type=~~phases~~ for help
   SEQUENCE EXECUTED: work -> shop
------------------------------------------------------------------
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
     csmake: Passed
------------------------------------------------------------------
     End csmake - version 1.3.2
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)

So here we see that if we work and then shop again, we can be successful.

What is going on here?  We have a couple of modules that work together by doing different parts of work for different phases.

At this point, you should be able to try some different combinations from the command line with csmake and your make file, possibly define some sequences in the ~~phases~~ section as csmake suggests, etlc.

To demonstrate how to do a sequence in the ~~phases~~ section, you would simply add **sequence and sequence lines like:
[~~phases~~]
shop=Purchase items for each defined step
return=Return all the items for each defined step
consume=Eat the items from each step
work=Earn more resources to make shopping successful
**sequences=
    work -> shop: Simple week of working and shopping
    consume -> work -> shop: Hungry week where we eat, work and shop

Then when you execute a csmake command like we did just above, you would see at the end:
SEQUENCE EXECUTED: work -> shop
   Simple week of working and shopping

Instead of a "WARNING" like above.

 

That's it!  Mess around with your project, try various things out, add modules if you like, add a way to reset your wallet (like a "clean" method), etc.

<sub>This material is under the GPL v3 license:

<sub>(c) Copyright 2017 Hewlett Packard Enterprise Development LP

<sub>This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

<sub>This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
Public License for more details.

<sub>You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

