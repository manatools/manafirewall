# Find if a Python 3 module is installed.
# Usage: find_python3_module(<module> [REQUIRED])
# Sets PY_<MODULE_UPPER> to the module location on success.
function(find_python3_module module)
	string(TOUPPER ${module} module_upper)
	if(NOT PY_${module_upper})
		if(ARGC GREATER 1 AND ARGV1 STREQUAL "REQUIRED")
			set(${module}_FIND_REQUIRED TRUE)
		endif()
		# A module's location is usually a directory, but for binary modules
		# it's a .so file.
		execute_process(
			COMMAND "${Python3_EXECUTABLE}" "-c"
				"import re, ${module}; print(re.compile('/__init__.py.*').sub('', ${module}.__file__))"
			RESULT_VARIABLE _${module}_status
			OUTPUT_VARIABLE _${module}_location
			ERROR_QUIET
			OUTPUT_STRIP_TRAILING_WHITESPACE)
		if(NOT _${module}_status)
			set(PY_${module_upper} ${_${module}_location} CACHE STRING
				"Location of Python 3 module ${module}")
		endif()
	endif()
	find_package_handle_standard_args(PY_${module} DEFAULT_MSG PY_${module_upper})
endfunction()
