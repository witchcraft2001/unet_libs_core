.PHONY: gen check check-bindings check-dlls update-dlls

gen:
	tools/gen_bindings.py gen

check: check-bindings check-dlls

check-bindings:
	tools/gen_bindings.py check

check-dlls:
	tools/check_dlls.py

update-dlls:
	tools/update_dlls.sh
