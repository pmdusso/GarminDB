#
# This Makefile automates running tests for the project.
#

PROJECT_BASE ?= $(CURDIR)/../.
export VENV=$(PROJECT_BASE)/.venv

include $(PROJECT_BASE)/defines.mk
include analysis_groups.mk


DB_TEST_GROUPS=garmin_db activities_db monitoring_db garmin_summary_db summary_db
DB_OBJECTS_TEST_GROUPS=garmin_db_objects
FILE_PARSE_TEST_GROUPS=fit_file tcx_loop tcx_file profile_file
ALL_TEST_GROUPS=$(DB_TEST_GROUPS) $(DB_OBJECTS_TEST_GROUPS) $(FILE_PARSE_TEST_GROUPS)
MANUAL_TEST_GROUPS=copy
BASE_TESTGROUP=config module_versions
TEST_GROUPS=$(DB_TEST_GROUPS) $(DB_OBJECTS_TEST_GROUPS) $(FILE_PARSE_TEST_GROUPS) $(MANUAL_TEST_GROUPS) $(BASE_TESTGROUP)

#
# Over all targets
#
all: $(ALL_TEST_GROUPS) analysis

db: $(DB_TEST_GROUPS)

manual: $(MANUAL_TEST_GROUPS)

file_parse: $(FILE_PARSE_TEST_GROUPS)

db_objects: $(DB_OBJECTS_TEST_GROUPS)

verify_commit: module_versions db_objects analysis

clean:
	echo "Cleaning test"
	rm -f *.pyc
	rm -f *.log
	rm -f *.txt
	rm -rf __pycache__

#
# Targets for testing smaller slices of functionality.
#
$(TEST_GROUPS):
	$(PYTHON_PATH) test_$@.py

test_%:
	$(PYTHON_PATH) -m unittest -v $@

# pytest analysis suite -- per-file to avoid the two models.py collision
# (garmindb/analysis/models.py vs garmindb/data/models.py share a module name).
analysis:
	@set -e; for t in $(ANALYSIS_SAFE); do \
	  echo "== pytest $$t =="; \
	  $(PYTHON_PATH) -m pytest -p no:cacheprovider -q $$t.py; \
	done

# Same suite, restricted to tests needing a real ~/.GarminDb config / DB.
analysis_manual:
	@set -e; for t in $(ANALYSIS_MANUAL); do \
	  echo "== pytest $$t (manual) =="; \
	  $(PYTHON_PATH) -m pytest -p no:cacheprovider -q $$t.py; \
	done

.PHONY: all db file_parse db_objects clean analysis analysis_manual
