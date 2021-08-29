#!/bin/bash
# <copyright>
# (c) Copyright 2021 Autumn Patterson
# (c) Copyright 2018 Cardinal Peak Technologies
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


set -e

#This is an executable script that executes the
#csmake testing
TEST_RESULTS=test-results

#To get a fresh set of test results
rm -rf $TEST_RESULTS
mkdir  $TEST_RESULTS

COVERAGE="python -m Csmake._vendor.coverage run -a --branch"

function test-passed {
    echo "========================================================"
    echo "   $1 TEST - PASSED"
}
function test-failed {
    echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    echo "   $1 TEST - FAILED"
    return 1
}

function exec-cmd {
    echo ""
    echo "################################################################"
    echo "       Test: $1"
    echo "       $2"
    return $($COVERAGE $2 > $TEST_RESULTS/$1.out)
}

# Test Harness
function dotest-default {
    CMD="./csmake --dev-output --debug --makefile=$2 --modules-path=:testmodules$4 $3 "
    if exec-cmd $1 "$CMD"
    then
        test-passed
    else
        test-failed
    fi
}

function dotest {
    CMD="./csmake --dev-output --debug --makefile=$2 --modules-path=:testmodules$5 --command=$3 $4"
    if exec-cmd $1 "$CMD"
    then
        test-passed
    else
        test-failed
    fi
}

function dotest-fail {
    CMD="./csmake --dev-output --debug --makefile=$2 --modules-path=:testmodules$5 --command=$3 $4"
    if exec-cmd $1 "$CMD"
    then
        test-failed
    else
        test-passed
    fi
}

function dotest-cmp {
    CMD="./csmake --quiet --makefile=$2 --modules-path=:testmodules$6 --command=$3 $4"
    if exec-cmd $1 "$CMD"
    then
        if [ "" == "$5" ]
        then
            if [ "`wc -c $TEST_RESULTS/$1.out | cut -d' ' -f 1`" == "0" ]
            then
                test-passed
                return 0
            fi
        fi
        if echo "$5" | diff - $TEST_RESULTS/$1.out
        then
            test-passed
        else
            echo "%%% Comparison failed: $5"
            test-failed
        fi
    else
        test-failed
    fi
}

function dounit {
    CMD="./csmake --dev-output --debug --command=$1 test"
    echo ""
    echo "#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#"
    echo "      Unit testing: $1"
    echo "      $CMD"
    if $CMD > $TEST_RESULTS/$1.out 2>&1
    then
        test-passed
    else
        test-failed
    fi
}

#Do some basic command line info tests
if exec-cmd list-shell-type "./csmake --list-type Shell"
then
    test-passed
else
    test-failed
fi

if exec-cmd test-short-help "./csmake --help"
then
    test-passed
else
    test-failed
fi

if exec-cmd test-verbose-help "./csmake --help --verbose"
then
    test-passed
else
    test-failed
fi

if exec-cmd test-long-help "./csmake --help-long"
then
    test-passed
else
    test-failed
fi

if exec-cmd test-no-chatter-csmakefile "./csmake  --modules-path=:testmodules --no-chatter --csmakefile=test.csmake build"
then
    test-passed
else
    test-failed
fi


#To run the current set of unit tests
#The filetracker testing is split in a couple of different runs
#This reports the coverage in a sane way
dounit test-filetracker
dounit test-csmakemodule

python -m Csmake._vendor.coverage erase

#Specification tests - testing correctness of csmake running specifications
dotest-default basic-with-build-phase test.csmake build
dotest-default basic-with-default-phase test.csmake
dotest-fail basic-failure test.csmake failing
dotest skip-with-unexpected-phase test.csmake skiptest xyzzy
dotest-default skip-with-no-phase test.csmake skiptest
dotest skip-with-standard-phase test.csmake skiptest build
dotest subclass-then-class test.csmake test-sub build
dotest multicommand test.csmake test,all,another build

dotest parallel test.csmake parallel build
dotest nested-parallel test.csmake nested-parallel build

#Test shell sections
dotest-default shell-hello test-shell.csmake build
dotest-default shell-hello-none test-shell.csmake xyzzy
dotest-cmp shell-hello-build test-shell.csmake default build "Hello, csmake!"
dotest-cmp shell-hello-clean test-shell.csmake default clean "Goodbye, csmake!"
dotest-cmp shell-hello-buildme test-shell.csmake default buildme "Hello, me"
dotest-cmp shell-hello-cleanme test-shell.csmake default cleanme "Goodbye, me"
dotest-cmp shell-hello-other test-shell.csmake default other "csmake is doing what it wants to do"
dotest-fail shell-hello-fail test-shell.csmake default failing
dotest shell-file-map-clean test-shell.csmake shell-clean-file-tracking clean
dotest shell-file-map-clean test-shell.csmake shell-clean-file-tracking messaround
dotest shell-file-map-nonexec test-shell.csmake shell-clean-file-tracking nothing
dotest shell-simple-map test-shell.csmake test-mapper build
dotest shell-ensure-map-skipped test-shell.csmake test-map-in-different-phase build
dotest-fail fail-required-for-map test-shell.csmake test-map-in-different-phase blasted
dotest-cmp basic-linepad test-shell.csmake test-basic-linepad build "1  2  3  4  5  6  7  8  9  "
dotest-cmp multiphase-ean test-shell.csmake test-multiphase ean ""
dotest-cmp multiphase-cle test-shell.csmake test-multiphase cle ""
dotest-cmp multiphase-test test-shell.csmake test-multiphase test "Yes"
dotest-cmp multiphase-build test-shell.csmake test-multiphase build "Yes"
dotest-cmp multiphase-blah test-shell.csmake test-multiphase blah "Yes"
dotest-cmp multiphase-clean test-shell.csmake test-multiphase clean "Clean!"
dotest-cmp multiphase-mean test-shell.csmake test-multiphase mean "Clean!"
dotest-cmp multiphase-blahblah test-shell.csmake test-multiphase blahblah "Clean!"
dotest-cmp multiphase-fightintest test-shell.csmake test-multiphase fightintest "Clean!"
dotest-cmp multiphase-noverify test-shell.csmake test-multiphase noverify "No Verify"
dotest-cmp multiphase-this test-shell.csmake test-multiphase this "No Verify"
dotest-cmp multiphase-section test-shell.csmake test-multiphase section "No Verify"
dotest shellenv-assurance test-shell.csmake test-shellenv build

dotest-cmp onexit testOnExit.csmake default build "_onExit called"
dotest-cmp onexit-clean testOnExit.csmake default "build clean" ""
dotest-cmp onexit-another testOnExit.csmake another build "Another's _onExit called"
dotest-cmp onexit-many-anothers testOnExit.csmake "another,another,another" build "Another's _onExit called
Another's _onExit called
Another's _onExit called"
dotest-cmp onexit-many-anothers-clean testOnExit.csmake "another,another,another" "build clean" ""
dotest-cmp shell-percent test-shell.csmake test-percent-escaping build "%"
dotest-cmp shell-percent test-shell.csmake echo-percent-aspect build "%"

#Test shell Aspects
dotest-cmp shellaspect-repeatadvice test-shell.csmake repeat-aspect build "Before basic-aspect
Actual shell
After basic-aspect, before end
Actual shell
After basic-aspect, before end
After basic-aspect"

#Test ShellToEnvironment
dotest-fail ShellToEnvironmentFail test-ShellToEnvironment.csmake default build
MYSHELLVAR=blah dotest-cmp ShellToEnvironmentPass test-ShellToEnvironment.csmake default build "blah"
MYSHELLVAR=this dotest-cmp ShellToEnvironmentAnotherDefault test-ShellToEnvironment.csmake another build "default:this"
MYOTHERVAR=notdefault MYSHELLVAR=that dotest-cmp ShellToEnvironmentAnotherDefault test-ShellToEnvironment.csmake another build "notdefault"

#Test metadata
dotest-default metadata-twolevels testmetadata.csmake
dotest-cmp metadata-env-values testmetadata.csmake "do-env,setup,showmetadata" clean "my-copyright"
dotest-fail metadata-env-values-fail testmetadata.csmake "do-env,setup,showmetadata,do-meta,showmetadata" ""
dotest metadata-non-semantic-version testmetadata.csmake bad-metadata-test default
dotest-cmp versioning-mods testmetadata.csmake test-versioning prep "9!~111.123+xyzzy"

#Test file tracking
dotest file-before-metadata test-filetracking.csmake file-before-metadata build
dotest-cmp files-kept-thru-metadata test-filetracking.csmake files-kept-thru-metadata build "RUNTESTS.sh"
dotest-cmp ensure-files-not-kept-thru-metadata test-filetracking.csmake ensure-files-not-kept-thru-metadata build ""

#Test TestPython
dotest-default test-TestPython test-TestPython.csmake
dotest-fail test-TestPython-failure test-TestPython.csmake show-failure test
dotest-fail test-TestPython-coverage test-TestPython.csmake show-bad-coverage test
dotest-fail test-TestPython-file-coverage test-TestPython.csmake show-bad-file-coverage test
dotest-fail test-TestPython-insufficient test-TestPython.csmake show-unsufficient test

#Test **phases
dotest-cmp test-phase-shift test.csmake test-phase-shift build "phase: special"
dotest-cmp test-phase-unshifted test.csmake test-phase-shift special "phase: special"
dotest-cmp test-another-phase-shift test.csmake test-another-phase-shift xyzzy "phase: build"
dotest-cmp test-phase-shift-with-aspects test.csmake test-phase-shift-with-aspects build "phase: aspect, start
phase: special
phase: aspect, passed
phase: aspect, end"
dotest-cmp test-phase-shift-with-aspects-section test.csmake test-phase-shift-with-aspects aspect "phase: aspect, start
phase: build
phase: aspect, passed
phase: aspect, end"

#Test nested csmake calls
dotest-default test-nested test-nested.csmake build

#####################################
# Testing footer
echo ""
echo "()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()()"
echo "     Testing completed"
echo "         Output is in '$TEST_RESULTS'"
echo "             Each test has a file named for the test followed by .out"
echo ""
echo "     Test Coverage    *Not including unit testing"
python -m Csmake._vendor.coverage report -m

echo " "
echo "nunununununununununununununununununununununununununu"
echo "nunununu   Testing Completed Successfully   nunununu"
echo "nunununununununununununununununununununununununununu"
