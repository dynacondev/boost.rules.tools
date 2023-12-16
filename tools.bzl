# Building boost results in many warnings. Downstream users won't be interested, so just disable them.
default_copts = select({
    "@platforms//os:windows": ["/W0"],
    "//conditions:default": ["-w"],
})

default_defines = select({
    "@boost.rules.tools//:windows_x86_64": ["BOOST_ALL_NO_LIB"],  # Turn auto_link off in MSVC compiler
    "//conditions:default": [],
})

def boost_library(
        name,
        defines = [],
        includes = ["include"],
        hdrs = [],
        srcs = [],
        copts = [],
        exclude_hdr = [],
        exclude_src = [],
        visibility = ["//visibility:public"],
        alias_repo_name = None,
        no_alias = False,
        **kwargs):
    if visibility == ["//visibility:public"] and not no_alias:
        if alias_repo_name == None:
            alias_repo_name = name
        native.alias(
            name = "boost." + alias_repo_name,
            actual = "@boost." + alias_repo_name + "//:" + name,
            visibility = ["//visibility:public"],
        )
    return native.cc_library(
        name = name,
        visibility = visibility,
        defines = default_defines + defines,
        includes = includes,
        hdrs = native.glob(
            ["include/boost/**"],
            exclude = exclude_hdr,
            allow_empty = True,
        ) + hdrs,
        srcs = native.glob(
            ["src/*"],
            exclude = ["**/*.asm", "**/*.S", "**/*.doc"] + exclude_src,
            allow_empty = True,
        ) + srcs,
        copts = default_copts + copts,
        **kwargs
    )

def boost_test(
        name,
        size = "small",
        srcs = [],
        exclude_src = [],
        deps = [],
        file_extensions = ".cpp",
        **kwargs):
    native.cc_test(
        name = name,
        size = size,
        srcs = srcs + [name + file_extensions] + native.glob(
            ["**/*.hpp"],
            exclude = exclude_src,
            allow_empty = True,
        ),
        deps = deps,
        **kwargs
    )
    return ":" + name

def boost_test_set(
        names,
        size = "small",
        srcs = [],
        exclude_src = [],
        deps = [],
        file_extensions = ".cpp",
        **kwargs):
    test_targets = []
    for name in names:
        boost_test(name = name, size = size, srcs = srcs, exclude_src = exclude_src, deps = deps, file_extensions = file_extensions, **kwargs)
        test_targets.append(":" + name)
    return test_targets

# def boost_test(
#         name,
#         size = "small",
#         srcs = [],
#         exclude_src = [],
#         deps = [],
#         expectFail = False,
#         **kwargs):
#     if expectFail:
#         # Generate a custom script that inverts the test result
#         test_wrapper_name = name + "_wrapper.sh"
#         native.genrule(
#             name = test_wrapper_name,
#             outs = [test_wrapper_name],
#             cmd = "echo '#!/bin/bash' > $@ && " +
#                   "echo './$(location :%s)' >> $@ && " % name +
#                   "echo 'exit $((! $?))' >> $@",
#             tools = [":" + test_wrapper_name],
#             executable = True,
#         )

#         test_target = ":" + test_wrapper_name
#     else:
#         test_target = ":" + name

#     native.cc_test(
#         name = name,
#         size = size,
#         srcs = srcs + [name + ".cpp"] + native.glob(
#             ["**/*.hpp"],
#             exclude = exclude_src,
#             allow_empty = True,
#         ),
#         deps = deps,
#         **kwargs
#     )

#     return test_target
