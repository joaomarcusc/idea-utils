#!/usr/bin/env python
import os,sys
from lxml import etree
import re

def pathsplit(path):
    """
    Split a path into an array of path components, using the file separator
    ('/' on POSIX systems, '\' on Windows) that's appropriate for the
    underlying operating system. Does not take drive letters into account.
    If there's a Windows drive letter in the path, it'll end up with the
    first component.

    :Parameters:
        path : str
            path to split. Can be relative or absolute

    :rtype:  list
    :return: a list of path components
    """
    result = []
    (head, tail) = os.path.split(path)

    if (not head) or (head == path):
        # No file separator. Done.
        pass

    else:
        result = pathsplit(head)

    if tail:
        result += [tail]

    return result

def __find_matches(pattern_pieces, directory):
    """
    Used by eglob.
    """
    import glob

    result = []
    if not os.path.isdir(directory):
        return []

    piece = pattern_pieces[0]
    last = len(pattern_pieces) == 1
    if piece == '**':
        if not last:
            remaining_pieces = pattern_pieces[1:]

        for root, dirs, files in os.walk(directory):
            if last:
                # At the end of a pattern, "**" just recursively matches
                # directories.
                result += [root]
            else:
                # Recurse downward, trying to match the rest of the
                # pattern.
                sub_result = __find_matches(remaining_pieces, root)
                for partial_path in sub_result:
                    result += [partial_path]

    else:
        # Regular glob pattern.

        matches = glob.glob(os.path.join(directory, piece))
        if len(matches) > 0:
            if last:
                for match in matches:
                    result += [match]
            else:
                remaining_pieces = pattern_pieces[1:]
                for match in matches:
                    sub_result = __find_matches(remaining_pieces, match)
                    for partial_path in sub_result:
                        result += [partial_path]

    # Normalize the paths.

    for i in range(len(result)):
        result[i] = os.path.normpath(result[i])

    return result

def eglob(pattern, directory='.'):
    """
    Extended glob function that supports the all the wildcards supported
    by the Python standard ``glob`` routine, as well as a special "**"
    wildcard that recursively matches any directory. Examples:
    
      +--------------+--------------------------------------------------------+
      | \*\*/\*.py   | all files ending in '.py' under the current directory  |
      +--------------+--------------------------------------------------------+
      | foo/\*\*/bar | all files name 'bar' anywhere under subdirectory 'foo' |
      +--------------+--------------------------------------------------------+

    :Parameters:
        pattern : str
            The wildcard pattern. Must be a simple pattern with no directories.

        directory : str
            The directory in which to do the globbing.

    :rtype:  list
    :return: A list of matched files, or an empty list for no match
    """
    pieces = pathsplit(pattern)
    return __find_matches(pieces, directory)

class Global(object):
    src_to_target = {
        "/src/": "/",
        "main/resources/": "classes/",
        "main/webapp/": ""
    }

    src_to_target_props = {
        "/src/": "/",
        "main/resources/": "WEB-INF/classes/",
        "main/webapp/": ""
    }

def filter_property_resources(project_dir, target_dir, map_replace):
    files = []
    for file in eglob("**/*.properties", project_dir):
        target_file = file
        target_file = target_file.replace(project_dir,target_dir)
        if "/test/" in target_file:
            continue
        for key in Global.src_to_target_props:
            target_file = target_file.replace(key, Global.src_to_target_props[key])
        if not os.path.exists(target_file):
            continue
        print target_file
        file_str = open(target_file).read()
        for key in map_replace:
            file_str = file_str.replace("${{{0}}}".format(key),map_replace[key])
        f = open(target_file,"w+")
        f.write(file_str)
        f.close()

def filter_web_resources(project_dir, target_dir, resource_dirs, includes, excludes, map_replace):
    files = []
    for resource_dir in resource_dirs:
        for include in includes:
            full_path = os.path.join(project_dir, resource_dir)
            files += [x for x in eglob(include, full_path)]
    for resource_dir in resource_dirs:
        for exclude in excludes:
            full_path = os.path.join(project_dir, resource_dir)
            files -= [x for x in eglob(include, full_path)]
    for file in files:
        target_file = file
        target_file = target_file.replace(project_dir,target_dir)
        for key in Global.src_to_target:
            target_file = target_file.replace(key, Global.src_to_target[key])
        print target_file
        file_str = open(target_file).read()
        for key in map_replace:
            file_str = file_str.replace("${{{0}}}".format(key),map_replace[key])
        f = open(target_file,"w+")
        f.write(file_str)
        f.close()

def strip_ns(xml_string):
    return re.sub('xmlns="[^"]+"', '', xml_string)


def properties_resource_filter(project_dir, target_dir, profile):
    doc = etree.fromstring(strip_ns(open(os.path.join(project_dir,"pom.xml")).read()))
    profile_node = doc.xpath("profiles/profile[id/text()='{0}']".format(profile))
    if not profile_node:
        return
    profile_node = profile_node[0]
    properties_node = profile_node.find("properties")
    prop_map = {}
    for prop_node in properties_node:
        prop_map[prop_node.tag] = prop_node.text

    filter_property_resources(project_dir, target_dir, prop_map)

def web_resource_filter(project_dir, target_dir, profile):
    doc = etree.fromstring(strip_ns(open(os.path.join(project_dir,"pom.xml")).read()))
    profile_node = doc.xpath("profiles/profile[id/text()='{0}']".format(profile))
    if not profile_node:
        return
    profile_node = profile_node[0]
    properties_node = profile_node.find("properties")
    prop_map = {}
    for prop_node in properties_node:
        prop_map[prop_node.tag] = prop_node.text

    maven_war_plugins = doc.xpath("build/plugins/plugin[artifactId/text()='maven-war-plugin' and groupId/text()='org.apache.maven.plugins']")
    for maven_war_plugin in maven_war_plugins:
        resources = maven_war_plugin.xpath("configuration/webResources/resource[filtering/text()='true']")
        for resource in resources:
            resource_dir = resource.xpath("directory/text()")
            includes = resource.xpath("includes/include/text()")
            excludes = resource.xpath("excludes/exclude/text()")
            if not resource_dir or (not includes and not excludes):
                continue
            resource_dirs = resource_dir[0].split(",")

            for resource_glob in resource_dirs:
                filter_web_resources(project_dir, target_dir, resource_dirs, includes, excludes, prop_map)

if __name__ == "__main__":
    properties_resource_filter(sys.argv[1], sys.argv[2], sys.argv[3])
    web_resource_filter(sys.argv[1],sys.argv[2],sys.argv[3])
