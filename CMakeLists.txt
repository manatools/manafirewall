if(POLICY CMP0048)
	cmake_policy(SET CMP0048 NEW)
endif(POLICY CMP0048)

project(manafirewall VERSION 0.0.3 LANGUAGES NONE)
cmake_minimum_required(VERSION 3.4)

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake")

find_package(PythonInterp 3.4 REQUIRED)
find_package(Gettext)

execute_process(COMMAND ${PYTHON_EXECUTABLE} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(), end='')" OUTPUT_VARIABLE PYTHON_INSTALL_DIR)
string(REGEX REPLACE "\n$" "" ${PYTHON_INSTALL_DIR} "${PYTHON_INSTALL_DIR}")
execute_process(COMMAND ${PYTHON_EXECUTABLE} -c "import sys; sys.stdout.write('%s.%s' % (sys.version_info.major, sys.version_info.minor))" OUTPUT_VARIABLE PYTHON_MAJOR_DOT_MINOR_VERSION)
message(STATUS "Python install dir is ${PYTHON_INSTALL_DIR}")

option(CHECK_RUNTIME_DEPENDENCIES "Verify the presence of runtime-only dependencies?" ON)

if(CHECK_RUNTIME_DEPENDENCIES)
	include(FindPythonModule)

	# Find the firewall module
	find_python_module(firewall REQUIRED)

	# Find yui module
	find_python_module(yui REQUIRED)

	# Find yui module
	find_python_module(manatools REQUIRED)

	# Find yaml module
	find_python_module(yaml REQUIRED)

endif(CHECK_RUNTIME_DEPENDENCIES)

# Set install dirs.
set(CMAKE_INSTALL_BINDIR "${CMAKE_INSTALL_PREFIX}/bin")
set(CMAKE_INSTALL_DATAROOTDIR "${CMAKE_INSTALL_PREFIX}/share")
set(CMAKE_INSTALL_LOCALEDIR "${CMAKE_INSTALL_DATAROOTDIR}/locale")
set(CMAKE_INSTALL_FULL_SYSCONFDIR "/etc" CACHE PATH "sysconfig directory (default /etc)")

# Configure files
configure_file(${CMAKE_SOURCE_DIR}/manafirewall/version.py.in ${CMAKE_BINARY_DIR}/manafirewall/version.py @ONLY)

# Build and install translations
if(GETTEXT_FOUND)
	add_subdirectory(po)
endif(GETTEXT_FOUND)

# Installing application code
install(PROGRAMS ${CMAKE_SOURCE_DIR}/scripts/manafirewall DESTINATION ${CMAKE_INSTALL_BINDIR})
file(GLOB_RECURSE PY_SRC LIST_DIRECTORIES false RELATIVE ${CMAKE_SOURCE_DIR} manafirewall/*.py)
install(FILES ${PY_SRC} ${CMAKE_BINARY_DIR}/manafirewall/version.py DESTINATION ${PYTHON_INSTALL_DIR}/manafirewall)

# Installing data files
install(FILES ${CMAKE_SOURCE_DIR}/share/metainfo/org.mageia.manafirewall.metainfo.xml DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/metainfo)

install(FILES ${CMAKE_SOURCE_DIR}/share/applications/org.mageia.manafirewall.desktop DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/applications)

install(FILES ${CMAKE_SOURCE_DIR}/share/images/256x256/manafirewall.png DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/icons/hicolor/256x256/apps RENAME manafirewall.png)

