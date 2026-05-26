# Bash tab completion for csmake
#
# Installation:
#   System-wide:  sudo cp csmake-completion.bash /etc/bash_completion.d/csmake
#   Per-user:     echo 'source /path/to/bash/csmake-completion.bash' >> ~/.bashrc
#
# Requires Python 3 (already required by csmake itself).
# The bash-completion package is recommended for _init_completion; a fallback
# is provided for environments without it.

# Query the csmakefile and print one result per line.
# Usage: _csmake_query <phases|commands|sequences> <makefile-path>
_csmake_query() {
    python3 -c '
import configparser, sys

query    = sys.argv[1]
makefile = sys.argv[2]

p = configparser.RawConfigParser()
p.optionxform = str
try:
    p.read(makefile)
except Exception:
    sys.exit(0)

if query == "phases":
    if p.has_section("~~phases~~"):
        for k in p.options("~~phases~~"):
            if not k.startswith("**") and not k.startswith("__"):
                print(k)

elif query == "commands":
    for s in p.sections():
        if s.startswith("command@") and "~~" not in s:
            name = s[len("command@"):]
            if name:
                print(name)

elif query == "sequences":
    if p.has_section("~~phases~~") and p.has_option("~~phases~~", "**sequences"):
        raw = p.get("~~phases~~", "**sequences")
        for line in raw.splitlines():
            line = line.strip()
            if "->" in line and ":" in line:
                print(line.split(":")[0].strip())
' "$1" "$2" 2>/dev/null
}

# Walk the already-typed words to find the effective --makefile/--csmakefile value.
_csmake_find_makefile() {
    local -a words=("$@")
    local makefile="./csmakefile"
    local i
    for ((i = 1; i < ${#words[@]} - 1; i++)); do
        case "${words[i]}" in
            --makefile=*|--csmakefile=*)
                makefile="${words[i]#*=}"
                break
                ;;
            --makefile|--csmakefile)
                ((i++))
                [[ $i -lt ${#words[@]} ]] && makefile="${words[i]}"
                break
                ;;
        esac
    done
    printf '%s' "$makefile"
}

_csmake() {
    local cur prev words cword
    if declare -f _init_completion > /dev/null 2>&1; then
        _init_completion || return
    else
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    fi

    local makefile
    makefile=$(_csmake_find_makefile "${words[@]}")

    # ----------------------------------------------------------------
    # --option value   (space-separated form, prev is the option name)
    # ----------------------------------------------------------------
    case "$prev" in
        --makefile|--csmakefile|--configuration|--log|--replay)
            COMPREPLY=($(compgen -f -- "$cur"))
            return
            ;;
        --command)
            COMPREPLY=($(compgen -W "$(_csmake_query commands "$makefile")" -- "$cur"))
            return
            ;;
        --phase)
            COMPREPLY=($(compgen -W "$(_csmake_query phases "$makefile")" -- "$cur"))
            return
            ;;
        --results-dir|--working-dir|--modules-path)
            COMPREPLY=($(compgen -d -- "$cur"))
            return
            ;;
        --list-type|--capture-fd|--settings)
            return
            ;;
    esac

    # ----------------------------------------------------------------
    # --option=value   (= separator) and bare -- prefix
    # ----------------------------------------------------------------
    case "$cur" in
        --makefile=*|--csmakefile=*|--configuration=*|--log=*|--replay=*)
            local pfx="${cur%%=*}="
            COMPREPLY=($(compgen -f -- "${cur#*=}"))
            COMPREPLY=("${COMPREPLY[@]/#/$pfx}")
            return
            ;;
        --command=*)
            local pfx="--command="
            COMPREPLY=($(compgen -W "$(_csmake_query commands "$makefile")" -- "${cur#*=}"))
            COMPREPLY=("${COMPREPLY[@]/#/$pfx}")
            return
            ;;
        --phase=*)
            local pfx="--phase="
            COMPREPLY=($(compgen -W "$(_csmake_query phases "$makefile")" -- "${cur#*=}"))
            COMPREPLY=("${COMPREPLY[@]/#/$pfx}")
            return
            ;;
        --results-dir=*|--working-dir=*|--modules-path=*)
            local pfx="${cur%%=*}="
            COMPREPLY=($(compgen -d -- "${cur#*=}"))
            COMPREPLY=("${COMPREPLY[@]/#/$pfx}")
            return
            ;;
        --*)
            local all_opts=(
                --help --help-long --help-all
                --list-types --list-type=
                --list-commands --list-phases
                --version
                --configuration= --makefile= --csmakefile=
                --command= --phase=
                --file-tracking --verbose --debug --quiet
                --no-chatter --dev-output
                --log= --capture-fd= --settings= --replay=
                --modules-path= --results-dir= --working-dir=
                --keep-going
            )
            COMPREPLY=($(compgen -W "${all_opts[*]}" -- "$cur"))
            return
            ;;
        *)
            # Positional arguments are phases (and phase sequences typed incrementally).
            local phases
            phases=$(_csmake_query phases "$makefile")
            [[ -n "$phases" ]] && COMPREPLY=($(compgen -W "$phases" -- "$cur"))
            return
            ;;
    esac
}

complete -F _csmake csmake
