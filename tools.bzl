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
        **kwargs):
    return native.cc_library(
        name = name,
        visibility = visibility,
        defines = default_defines + defines,
        # includes = ["libs/%s/include" % boost_name] + includes,
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
