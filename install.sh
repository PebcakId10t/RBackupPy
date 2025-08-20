#!/usr/bin/env sh
# This installs a launcher script in your ~/bin or ~/.local/bin directory
# with the same name as the project.  It's meant for python projects that
# contain a main.py in the project root.  It calls main.py, passing it all
# args passed to the launcher.  It can optionally use a python venv if
# present in the project.

project_dir=$(dirname $(readlink -f "$0"))
project_name=$(basename ${project_dir})
entry_point="main.py"
venv_required=false

print_usage() {
    echo "usage: install.sh [-h] [-v] [-e <entry point>]" >&2
    echo "Create a launcher script for this project in your private bin/ dir" >&2
    echo "    -h    Print help" >&2
    echo "    -v    Project requires a venv (default: false)" >&2
    echo "          If required, there must be a venv located in venv/ or .venv/ at the project root." >&2
    echo "          If not required but present, the launcher script will still use the venv." >&2
    echo "    -e    Script entry point (default: main.py)" >&2
}

while getopts ":hve:" opt; do
    case ${opt} in
        h ) print_usage; exit 0;;
        v ) venv_required=true ;;
        e ) entry_point="${OPTARG}" ;;
        * ) echo "Unrecognized option '-${OPTARG}'" >&2; print_usage; exit 1;;
    esac
done

bins=("${HOME}/.local/bin" "${HOME}/bin")
for dir in "${bins[@]}"; do
    if [ -d "${dir}" ]; then
        bin="${dir}"
        break
    fi
done
unset dir bins
[ -z "${bin}" ] && echo "No private bin found (~/.local/bin, ~/bin)" && exit 1

venvs=('venv' '.venv')
for dir in "${venvs[@]}"; do
    if [ -d "${dir}" ]; then
        venv="${dir}"
        pypath="${project_dir}/${venv}/bin/python"
        break
    fi
done
unset dir venvs

if [ -z "${venv}" ] && [ "${venv_required}" = true ]; then
    echo "No venv (venv/, .venv/) - run 'python -m venv venv' and 'pip install -r requirements.txt'"
    exit 1
elif [ -z "${venv}" ]; then
    pypath="$(command -v python)"
fi

cat > "${bin}"/"${project_name}".sh << EOF
#!/usr/bin/env sh
if [ "\$1" = "push" ]; then
    shift
    ${pypath} ${project_dir}/${entry_point} -m push "\$@"
elif [ "\$1" = "pull" ]; then
    shift
    ${pypath} ${project_dir}/${entry_point} -m pull "\$@"
else
    ${pypath} ${project_dir}/${entry_point} "\$@"
fi
EOF
chmod +x "${bin}"/"${project_name}".sh
echo "'${project_name}.sh' created in '${bin}'"

unset bin venv pypath project_name project_dir entry_point venv_required
