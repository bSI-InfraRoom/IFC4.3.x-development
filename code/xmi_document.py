# @todo: double encoding e.g Role &amp;lt;&amp;gt;
# @todo: schema name not really discoverable
# @todo: ControlPointsList / ColourList : LIST [2:?] OF LIST [2:?]
# @todo: IfcClassificationReference.HasReferences self referential inverse
# @todo: schema namespace different in constraint expression

# CONFIGURATION
    
# currently not used
express_excluded_stereotypes = set((
    "propertyset", 
    "quantityset", 
    "penumtype", 
    "virtualentity"))
    
all_excluded_stereotypes = set((
    "virtualentity"))
    
included_statuses = set((
    "implemented", 
    "proposed", 
    "proposedmodification", 
    "deprecated", 
    "approved", 
    "candidate"))
    
REPO_URL = "https://github.com/buildingSMART/IFC4.3.x-development/edit/master/"

import os
import re
import sys
import html

import operator
import functools
import itertools
import subprocess

from collections import defaultdict, namedtuple, Counter

import xmi
import express

from md import markdown_attribute_parser

import logging
logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

# @todo schema name is hardcoded and not derived from the XMI package name for now
SCHEMA_NAME = "IFC4X3_DEV"

try:
    if os.environ.get("REPO_DIR"):
        repo_dir = "-C", os.environ.get("REPO_DIR")
    else:
        repo_dir = []
    sha = subprocess.check_output(["git", *repo_dir, "rev-parse", "--short", "HEAD"]).decode('ascii').strip()
    SCHEMA_NAME += f"_{sha}"
except: pass

def unescape(s):
    # @todo this is bizarre encoding, what happened here?
    return html.unescape(html.unescape(s.replace('xx38', '&')))

def float_international(s):
    return float(s.replace(',', '.'))
    
assocation_data = namedtuple("assocation_data", ("own_end", "type", "other_end", "asssocation"))

def yield_parents(node):
    yield node
    if node.parentNode:
        yield from yield_parents(node.parentNode)
        
def get_path(xmi_node):
    nodes = list(yield_parents(xmi_node.xml))
    def get_name(n):
        if n.attributes:
            v = n.attributes.get('name')
            if v: return v.value
    node_names = [get_name(n) for n in nodes]
    return node_names[::-1]
    
infinity = 1e9

where_pat = re.compile(r"'\w+\.(\w+(\.\w+)?)'")
def fix_schema_name(s):
    def repl(x):
        return "'%s.%s'" % (SCHEMA_NAME, x.group(1))
    return remove_linebreak_before_semi(re.sub(where_pat, repl, s))
    
def remove_linebreak_before_semi(s):
    lines = s.split('\n')
    if lines[-1] == ';':
        lines[-2] += ';'
        lines[-1:] = []
    return '\n'.join(lines)
    

class missing_markdown:
    def __init__(self, reason): self.reason = reason
    def __bool__(self): return False
    def __repr__(self): return self.reason
    def to_json(self):
        logging.warning(self.reason)
        return ''
        
        
class xmi_item:
    id = None
    type = None
    name = None
    definition = None
    node = None
    children = None
    stereotype = None
    document = None
    parent = None
    
    def __init__(self, type, name, definition, node, children = None, stereotype = None, document = None, parent = None, **kwargs):
        self.type, self.name, self.definition, self.node, self.children = type, name.strip(), definition, node, children or []
        self.children = [xmi_item(None, a, None, b, None, parent=self, document=document) for a, b in self.children]        
        self.stereotype = stereotype
        self.meta = kwargs
        self.document = document
        self.parent = parent
        if self.node:
            self.id = self.node.id or self.node.idref
            
    def _mdtype(self):
        return {
            "PT"    : "Types",
            "PSET"  : "PropertySets",
            "TYPE"  : "Types",
            "PENUM" : "Types" ,
            "SELECT": "Selects",
            "ENUM"  : "Types",
            "ENTITY": "Entities",
        }[self.parent.type if self.parent else self.type]
        
    def __iter__(self):
        return iter(self.children)
        
    def _get_documentation(self):
        if self.node:
            ds = (self.node/"documentation")
            if len(ds) == 1 and self.node.xml.tagName != 'element':
                return ds[0].value
            else:
                ps = (self.node/"properties")
                if ps:
                    return ps[0].documentation
                    
    def _get_package(self):
        is_sub = self.parent is not None
        return self.parent.path[-2] if is_sub else self.path[-2]
                    
    def _get_markdown(self, definition=False):
        if self.node:
            is_sub = self.parent is not None
            
            fn = self.parent.document.filename if is_sub else self.document.filename
            repo_root = os.path.join(os.path.abspath(os.path.dirname(fn)), '..')
            md_root = os.path.join(repo_root, 'docs')
            md_fn = None
            
            if self.parent and self.parent.type == "PSET" and self.type is None:
                # properties are not encoded into a definition of their pset
                # but rather are listed separately in a directory 
                is_sub = False
                md_fn = os.path.join(md_root, 'properties', self.name[0].lower(), self.name + ".md")
            else:
                md_root = os.path.join(md_root, 'schemas')
                for category in os.listdir(md_root):
                    for module in os.listdir(os.path.join(md_root, category)):
                        if module == self.package:
                            md_fn = os.path.join(md_root, category, module, self.mdtype, (self.parent.name if is_sub else self.name) + ".md")
                            break
                            
            if md_fn is None:
                return missing_markdown("Unable to locate markdown path")                        
            
            p = os.path.relpath(md_fn, start=repo_root).replace(os.sep, '/')
                                    
            if not os.path.exists(md_fn):
                return missing_markdown(REPO_URL + p + " does not exist")
            
            hname = 'Attributes' if not is_sub or self.parent.type == "ENTITY" else 'Items'
            md_parser = markdown_attribute_parser(open(md_fn, encoding='utf-8').read(), hname)
            
            if is_sub:                
                attrs = dict(md_parser)
                if md_parser.status.get("ALL") == "NO_HEADING":
                    return missing_markdown(REPO_URL + p + " has no '%s' heading" % sub_item_heading_name)
                    
                st = md_parser.status.get(self.name)
                if st and st[0] == "NO_CONTENT":
                    return missing_markdown(REPO_URL + p + "#L%d has no content" % st[1])
                elif st is None:
                    return missing_markdown(REPO_URL + p + " has no '%s' heading" % self.name)
                
                return attrs[self.name]
            else:
                d = md_parser.definition(short=definition)
                st = md_parser.status.get("DEFINITION")
                if st and st[0] == "NO_CONTENT":
                    return missing_markdown(REPO_URL + p + " has no content")
                else:
                    return d

                        
    def _get_markdown_definition(self):
        return self._get_markdown(definition=True)
        
    def _get_markdown_definition_html(self):
        # pip install Markdown
        import markdown
        
        md = self._get_markdown(definition=True)
        
        if not md: return md
        
        html = markdown.markdown(
            md,
            extensions=['tables', 'fenced_code']
        )
        
        return html
                        
    def _get_path(self):
        if self.node:
            return get_path(self.document.xmi.by_id[self.id])
        
    documentation = property(_get_documentation)
    markdown = property(_get_markdown)
    markdown_definition = property(_get_markdown_definition)
    markdown_definition_html = property(_get_markdown_definition_html)
    path = property(_get_path)
    package = property(_get_package)
    mdtype = property(_mdtype)
    
class xmi_document:

    def __init__(self, fn):    
    
        if isinstance(fn, str):
            self.filename = fn
            self.xmi = xmi.doc(fn)
        else:
            self.xmi = fn
            
        self.extract_associations()
        self.extract_associations(concepts=True)
        self.extract_order()
                
        # Assert that we indeed have all `included_packages` in the UML
        # packagenames_from_uml = set(map(operator.attrgetter('name'), self.xmi.by_tag_and_type["packagedElement"]["uml:Package"]))
        # assert len(included_packages - packagenames_from_uml) == 0
        
    def try_get_order(self, a):
        try:
            return int(self.xmi.tags['ExpressOrdering'][a.id or a.idref])
        except IndexError as e:
            # When no ordering is found in sequences where other elements do have
            # ordering, they are pushed to the back to be consistent with IFC4X3_RC1
            return infinity

        
    def skip_by_package(self, element):
        return "Views" in get_path(self.xmi.by_id[element.id or element.idref])
        
        
    def supertypes(self, eid):
        yield self.xmi.by_id[eid].name
        gs = self.xmi.by_id[eid] / "generalization"
        if gs:
            yield from self.supertypes(gs[0].general)

            
    def extract_associations(self, concepts=False):
        # Extract some data from the assocations for use later on
        
        if concepts:
            self.concepts = defaultdict(lambda: defaultdict(list))
            self.concept_associations = defaultdict(list)
        else:
            self.assocations = defaultdict(list)
            self.assoc_from = defaultdict(list)
            self.assoc_to = defaultdict(list)
        
        for assoc in self.xmi.by_tag_and_type["packagedElement"]["uml:AssociationClass" if concepts else "uml:Association"]:
            # @todo n-aray assocs
            
            mends = assoc/'memberEnd'
            ends = [self.xmi.by_id[mend.idref] for mend in mends]
            is_source = [e.xml.tagName == "ownedEnd" for e in ends]
            end_types = list(map(lambda c: (c|"type").idref, ends))
            try:
                end_type_names = list(map(lambda t: self.xmi.by_id[t].name, end_types))
            except KeyError as e:
                logging.warning("Encountered exception `%s' on %s", e, assoc)
                continue            
            
            if concepts:
                parent = get_path(assoc)[-2]
                
                self.concept_associations[parent].append(end_types)
                
                is_rooted = lambda tid: "IfcRoot" in self.supertypes(tid)
                sorted_type_ids = sorted(zip(map(is_rooted, end_types), end_types), reverse=True)
                sorted_type_ids = tuple(map(operator.itemgetter(1), sorted_type_ids))
                
                self.concepts[parent][sorted_type_ids[0]].extend(sorted_type_ids[1:])
                for other in sorted_type_ids[1:]:
                    self.concepts[parent][other].append(sorted_type_ids[0])
                    
            else:
                if len(ends) != 2:                    
                    logging.warning("Expeced two associations ends on %s", assoc)
                    continue
                
                c1, c2 = ends
                t1, t2 = end_types
                tv1, tv2 = end_type_names
                
                for is_s, from_id, to_id in zip(is_source, end_types, reversed(end_types)):
                    if is_s:
                        self.assoc_from[from_id].append(to_id)
                    else:
                        self.assoc_to[from_id].append(to_id)
                
                self.assocations[tv1].append(assocation_data(c2, self.xmi.by_id[t2], c1, assoc))
                self.assocations[tv2].append(assocation_data(c1, self.xmi.by_id[t1], c2, assoc))

        if concepts:
            for inter in self.xmi.by_tag_and_type["packagedElement"]["uml:Class"]:
                pt = get_path(inter)
                if "Views" in pt:
                    parent = pt[-2]
                    for ff, tt in itertools.product(self.assoc_to[inter.id], self.assoc_from[inter.id]):
                        self.concepts[parent][ff].append(tt)
                            

    def extract_order(self):
        self.order = {k: int(v) for k, v in self.xmi.tags["ExpressOrdering"].items()}
    
    def __iter__(self):
        """
        A generator that yields tuples of <a, b> with
        a: an element in EXPRESS_ORDER
        b: an type/entity/function definition string
        """
        
        for c in (self.xmi.by_tag_and_type["element"]["uml:Class"] + self.xmi.by_tag_and_type["element"]["uml:Interface"] + self.xmi.by_tag_and_type["element"]["uml:Enumeration"] + self.xmi.by_tag_and_type["element"]["uml:DataType"]):
        
            if self.skip_by_package(c):
                continue
                                               
            if "penum_" in c.name.lower():
                continue
                
            stereotype = (c/"properties")[0].stereotype if (c/"properties") else None
            if stereotype is not None: 
                stereotype = stereotype.lower()
                
            if stereotype in all_excluded_stereotypes:
                continue
                
            status = (c/"project")[0].status if (c/"project") else None
            if status is not None: 
                status = status.lower()
                
            if status not in included_statuses:
                continue
            
            if stereotype in {"express function", "express rule"}:
                
                yield xmi_item(
                    stereotype.split(" ")[1].upper(), 
                    unescape((c|"behaviour").value).split(" ")[1], 
                    fix_schema_name(unescape((c|"behaviour").value)) + ";", 
                    c, 
                    document=self
                )
                
            elif stereotype == 'predefinedtype':
                
                # A predefined type enumeration value, handled as part of 'ptcontainer'
                continue
                
                # NB: can have multiple dependency relationships...
                # yield xmi_item("PT", c.name, "", c, [], container=((c|"links")|"Dependency").start, document=self)
                
            elif stereotype is not None and (stereotype.startswith("pset_") or stereotype.startswith("qto_") or stereotype == "complexproperty"):
                
                if stereotype.startswith("qto_"):
                    stereotype = "QSET"
                elif stereotype.startswith("pset_"):
                    stereotype = "PSET"
                else:
                    stereotype = "CPROP"
                
                refs = None
                
                if stereotype == "PSET" or stereotype == "QSET":
                    try:
                        refs = self.concepts[(["Quantity", "Property"][stereotype == "PSET"]) + "SetsforObjects"].get(c.id or c.idref)
                    except ValueError as e:
                        print("WARNING:", c.name, "has no associated class", file=sys.stderr)
                        continue

                # TEMPORARY SKIP SOME OLD PSET DEFINITIONS
                if (c|"project").author == 'IQSOFT':
                    continue

                set_definition = []
                for attr in self.xmi.by_id[c.idref]/"ownedAttribute":
                    nm = attr.name
                    ty = self.xmi.by_id[(attr|"type").idref]
                    
                    if stereotype in ("PSET", "CPROP"):
                    
                        for b in ty/"templateBinding":
                            if b/"parameterSubstitution":
                                prop_type = self.xmi.by_id[b.signature].xml.parentNode.getAttribute('name')
                                prop_args = {}
                                for sub in b/"parameterSubstitution":
                                    formal = (self.xmi.by_id[sub.formal] | "ownedParameteredElement").name
                                    actual = self.xmi.by_id[sub.actual].name
                                    prop_args[formal] = actual
                                    
                                set_definition.append((nm, (prop_type, prop_args)))

                    else:
                        set_definition.append((nm, ty.name))

                yield xmi_item(
                    "CPROP" if stereotype == "CPROP" else "PSET", 
                    c.name, 
                    set_definition, 
                    c,
                    [(x.name, x) for x in c/("attribute")],
                    document=self, 
                    refs=refs,
                    stereotype=stereotype
                )
                
            elif c.xmi_type == "uml:DataType":
            
                dd = self.xmi.by_id[c.idref]
                try:
                    super = [t for t in c/"tag" if t.name == "ExpressDefinition"][0].value
                    super_verbatim = True
                except IndexError as e:
                    try:
                        super = self.xmi.by_id[(dd|"generalization").general].name
                        super_verbatim = False
                    except ValueError as ee:
                        # if the type does not have a generalization, let's assume it's one of EXPRESS' native types
                        logging.warning("No generalization found on %s, omitting", c)
                        continue
                
                cs = sorted(c/"constraint", key=lambda cc: float_international(cc.weight))
                constraints = map(lambda cc: "\t%s : %s;" % tuple(map(unescape, map(functools.partial(getattr, cc), ("name", "description")))), cs)            
                
                yield xmi_item("TYPE", c.name, express.simple_type(c.name, super, constraints, super_verbatim=super_verbatim), c, document=self)
                
            elif self.xmi.by_id[c.xmi_idref].xmi_type == "uml:Enumeration":
            
                values = [(x.name.split(".")[1], x) for x in self.xmi.by_tag_and_type["packagedElement"]["uml:Class"] if x.name.startswith(c.name+".")]

                get_attribute = lambda n: [x for x in self.xmi.by_idref[n.xmi_id] if x.xml.tagName == "attribute"][0]
                if not values:
                    values = [(x.name, get_attribute(x)) for x in self.xmi.by_id[c.xmi_idref]/"ownedLiteral"]
                    
                yield xmi_item(
                    "PENUM" if stereotype == "penumtype" or c.name.lower().startswith("penum_") else "ENUM", # <------- nb 
                    c.name, express.enumeration(c.name, [a for a, b in values]), c, values, document=self)
            
            elif stereotype == "express select" or stereotype == "select" or c.xmi_type == "uml:Interface":
                
                values = sorted(filter(lambda s: s != c.name, map(lambda s: self.xmi.by_id[s.start].name, c/"Substitution")))
                yield xmi_item("SELECT", c.name, express.select(c.name, values), c, document=self)
                
            # elif stereotype == "enumeration":
            # 
            #     
            #             
            #     values = map(operator.itemgetter(1), sorted(map(lambda a: (self.try_get_order(a), (a.name, a)), c/("attribute"))))
            #     yield xmi_item("ENUM", c.name, express.enumeration(c.name, [a for a, b in values]), c, values, document=self)
                
            elif stereotype == 'templatecontainer':

                nodes = [[x for x in self.xmi.by_idref[d.supplier] if x.xml.tagName == "element"][0] for d in self.xmi.by_tag_and_type["packagedElement"]["uml:Dependency"] if d.client==c.idref]
                values = [(n.name, n) for n in nodes]
                
                # NB This is actually a fix of the schema
                if c.name == "IfcPropertySetTemplateTypeEnum":
                    values.insert(0, ("NOTDEFINED", None))
                
                # @todo ExpressOrdering on <element>
                yield xmi_item("ENUM", c.name, express.enumeration(c.name, [a for a, b in values]), c, values, document=self)
            
            # elif stereotype == 'ptcontainer':
            # 
            #     old_c = None
            #     
            #     # NB This is actually a fix of the schema: Transfer IfcBuiltSystemTypeEnum children to IfcBuildingSystemTypeEnum
            #     try:
            #         if self.xmi.by_id[(c|"NoteLink").start].body == 'All Predefined Types Transferred to new enum with better name':
            #             old_c = c
            #             c = [x for x in self.xmi.by_tag_and_type["element"]["uml:Class"] if x.name == "IfcBuiltSystemTypeEnum"][0]
            #     except: pass
            #     
            #     children = []
            #     ids = [d.end for d in (c/"Dependency") if d.start == c.xmi_idref]
            #     if not ids:
            #         print("Warning, no dependency relationship for %s" % c.name)
            #         nodes = [x for x in self.xmi.by_tag_and_type["element"]["uml:Class"] if x.name.startswith(c.name + ".")]
            #         children = list(map(operator.itemgetter(1), sorted(map(lambda a: (self.try_get_order(a), (a.name.split('.')[1], a)), nodes))))
            #         values = [a for a, b in children]
            #     else:
            #         def get_element(id): 
            #             ns = [n for n in self.xmi.by_tag_and_type['element']['uml:Class'] if n.idref==id]
            #             if ns: return ns[0]
            #             else:
            #                 print("Warning, no uml:Class element for %s" % id)
            #         elems = list(filter(None, map(get_element, ids)))
            #         def get_stereotype(elem): return (elem/"properties")[0].stereotype if (elem/"properties") else None
            #         stereotypes = list(map(get_stereotype, elems))
            #         # pelems = [self.xmi.by_id[n.idref] for n in elems]
            #         # [self.skip_by_package(x) for x in pelems]
            #         # [(x|"project").status for x in elems]
            #         filtered_elems = [e for e,s in zip(elems, stereotypes) if s.lower() != 'virtualentity']
            #         children = [(e.name.split('.')[-1], e) for e in filtered_elems]
            #         # make unique by name
            #         children = [x for i,x in enumerate(children) if x[0] not in [y[0] for y in children[0:i]]]
            #         values = [a for a, b in children]
            #     
            #     if "USERDEFINED" not in values: values.append("USERDEFINED")
            #     if "NOTDEFINED" not in values: values.append("NOTDEFINED")
            #     
            #     if old_c:
            #         c = old_c
            #     
            #     yield xmi_item("ENUM", c.name, express.enumeration(c.name, values), c, children, document=self, stereotype="PREDEFINED_TYPE")

            elif stereotype is not None and (stereotype.startswith("pset") or stereotype == "$"):
                # Don't serialize psets to EXPRESS
                # @todo Some psets (and only psets) have their stereotype set to $, why?
                continue
                
            elif stereotype == "virtualentity":
            
                continue
                
            else:
            
                if not c.name.startswith("Ifc"):
                    # @tfk entities need to start with IFC or otherwise 'conceptual'?
                    continue
            
                is_abstract = (c/"properties")[0].isAbstract == "true" 
            
                attribute_names = set()
                attributes_optional = {}
                for la in c / ("attribute"):
                    iref = la.idref
                    a = self.xmi.by_id[iref]
                    n = a.name
                    attribute_names.add(n)

                attributes, inverses, derived, subtypes, supertypes, children = [], [], [], [], [], []
                
                for g in c/("Generalization"):
                    start, end = g.start, g.end
                    issub = start == c.idref
                    other = [start, end][issub]
                    other_name = self.xmi.by_id[other].name
                    [supertypes, subtypes][issub].append(other_name)
                    
                # In case of assymetric inverse relationships we need to find the
                # proper target element.
                assocs_by_name = self.assocations[c.name].copy()
                # count duplicate role names
                counter = Counter()
                counter.update(ass[0].name for ass in assocs_by_name)
                # flag duplicates
                duplicates = [ass[0].name is not None and counter[ass[0].name] > 1 for ass in assocs_by_name]
                # look up suppression tag
                suppressed = [self.xmi.tags['ExpressSuppressRel'].get(ass[2].id) == "YES" for ass in self.assocations[c.name]]
                # apply filter
                assocs_by_name = [a for a,d,s in zip(assocs_by_name, duplicates, suppressed) if not (d and s)]
                    
                for end_node, end_node_type, other_end, assoc_node in assocs_by_name:
                    try:
                        nm = end_node.name
                        assert nm
                    except:
                        continue
                        
                    try:
                        attr_name = other_end.name
                    except:
                        attr_name = None
                    

                    is_inverse = bool(self.xmi.tags['ExpressInverse'].get(end_node.id))
                    if is_inverse:
                        inverse_order = int(self.xmi.tags['ExpressOrderingInverse'][end_node.id])
                    
                    express_aggr = self.xmi.tags['ExpressAggregation'].get(end_node.id, "")
                    # It appears there is some inconsistency (IfcBSplineSurface.ControlPointList)
                    # where the definition is located on the association and not on the member ends
                    express_definition = self.xmi.tags['ExpressDefinition'].get(end_node.id) or \
                        self.xmi.tags['ExpressDefinition'].get(assoc_node.id)
                    is_optional = bool(self.xmi.tags['ExpressOptional'].get(end_node.id, False))
                    is_unique = bool(self.xmi.tags['ExpressUnique'].get(end_node.id, False))
                    
                    # @tfk this was misguided
                    # is_inverse |= assoc_node.xmi_id not in self.order
                        
                    # @tfk this is no longer working, rely fully on `express_aggr`
                    # if not is_inverse and end_node.isOrdered is not None:
                    #     express_aggr = "LIST" if end_node.isOrdered == "true" else "SET"
                        
                    if end_node/"lowerValue" and not express_aggr:
                        is_optional |= (end_node|"lowerValue").value == '0'
                        
                    bound = "[0:1]" if is_inverse else "[0:?]"
                    try:
                        lv = int((end_node|"lowerValue").value)
                        uv_s = (end_node|"upperValue").value
                        if uv_s == "*":
                            uv = "?"
                        else:
                            uv = int(uv_s)
                            if uv == -1: uv = "?"
                        bound = "[%s:%s]" % (lv, uv)
                    except: pass
                    attr_entity = end_node_type.name                
                        
                    # bound != "[0:?]" and 
                    # inverse attributes always aggregates?
                    if is_inverse and end_node.isOrdered is None and bound != "[1:1]":
                        express_aggr = "SET"
                        
                    is_optional_string = "OPTIONAL " if is_optional else ""

                    express_aggr_unique = "UNIQUE " if is_unique else ""
                    
                    if express_aggr:
                        attr_entity = "%s %s OF %s%s" % (express_aggr, bound, express_aggr_unique, attr_entity)
                        
                    if express_definition:
                        attr_entity = express_definition

                    if nm not in attribute_names:
                        if is_inverse: # or assoc_node.xmi_id not in order:
                            if attr_name is not None:
                                inverses.append((inverse_order, "\t%s : %s FOR %s;" % (nm, attr_entity, attr_name)))
                            else:
                                logging.warning("No role name in connector target for %s.%s" % (c.name, nm))
                        else:
                            attribute_order = self.order.get(assoc_node.xmi_id, None)
                            if attribute_order is None:
                                attribute_order = self.order.get(end_node.xmi_id, None)
                            if attribute_order is None:
                                logging.warning("No attribute order on %s.%s" % (c.name, nm))
                                attribute_order = 1000
                            attributes.append((attribute_order, (nm, is_optional_string + attr_entity)))
                            
                        children.append((nm, assoc_node))
                    else:
                        # mark as optional for when emitted as an UML attribute below
                        attributes_optional[nm] = is_optional
                        
                    # @tfk workaround for associations with the same name
                    attribute_names.add(nm)
                        
                for la in c/("attribute"):
                
                    iref = la.idref
                    a = self.xmi.by_id[iref]
                    is_optional = "ExpressOptional" in map(operator.attrgetter('name'), la/("tag"))
                    is_unique = bool(self.xmi.tags['ExpressUnique'].get(iref, False))
                    
                    bnds = la/"bounds"
                    express_aggr = la.tags().get("ExpressAggregation") or (bnds and bnds[0].upper and bnds[0].upper != '1')
                    if not express_aggr:
                        if bnds:
                            is_optional |= bnds[0].lower == '0'
                        is_optional |= attributes_optional.get(a.name, False)
                            
                    is_derived = a.isDerived == "true"
                    
                    if express_aggr is True and (la/"coords"):
                        express_aggr = "LIST" if (la/"coords")[0].ordered == "1" else "SET"
                    
                    if express_aggr:
                        bound = ""
                        try:
                            lv = int((a|"lowerValue").value)
                            uv_s = (a|"upperValue").value
                            if uv_s == "*":
                                uv = "?"
                            else:
                                uv = int(uv_s)
                                if uv == -1: uv = "?"
                            bound = "[%s:%s]" % (lv, uv)
                        except: continue
                    # or use order[iref]?
                    try:
                        ordering = int(la.tags()["ExpressOrdering"])
                    except KeyError as e:
                        ordering = 0
                    is_optional_string = "OPTIONAL " if is_optional else ""
                    n = a.name
                    try:
                        t = (a|"type").idref
                    except:
                        is_derived = len(la/"Constraint") == 1
                        if not is_derived:
                            logging.warning("Unable to find type of %s on %s", a, c)
                            continue
                        
                    if is_derived:
                        derive_def = unescape((la|"Constraint").notes)
                        if derive_def.startswith("%s : " % n):
                            logging.warning("Derived attribute definition for %s contains attribute name: %s", n, derive_def)
                            derive_def = derive_def[len(n) + 3:]
                        derived.append((ordering, "\t%s : %s;" % (n, derive_def)))
                        children.append((n, la))
                        continue
                    attribute_names.add(n)
                    
                    tv = express.ifc_name(self.xmi.by_id[t].name)
                    if express_aggr:
                        tv = "%s %s OF %s%s" % (express_aggr, bound, "UNIQUE " if is_unique else "", tv)
                    
                    override = la.tags().get("ExpressDefinition")
                    if override:
                        tv = override
                        is_optional_string = ""
                        
                    attributes.append((ordering, (n, is_optional_string + tv)))
                    
                    children.append((n, la))
                
                def trailing_semi_fix(s):
                    if s.endswith(';'):
                        logging.warning("Definition '%s' ends in semicolon", s)
                        return s[:-1]
                    else:
                        return s
                    
                cs = sorted(c/("constraint"), key=lambda cc: float_international(cc.weight))
                constraints_type_name_def = map(lambda cc: ((cc.type,) + tuple(map(trailing_semi_fix, map(unescape, map(functools.partial(getattr, cc), ("name", "description")))))), cs)
                constraints_by_type = defaultdict(list)
                for ct, cname, cdef in constraints_type_name_def:
                    if cdef.startswith("%s : " % cname):
                        logging.warning("Where clause for %s contains attribute name: %s", cname, cdef)
                        cdef = cdef[len(cname) + 3:]
                    cc = (cname.strip(), fix_schema_name(cdef))
                    constraints_by_type[ct].append(cc)

                attributes = map(operator.itemgetter(1), sorted(attributes))
                inverses = map(operator.itemgetter(1), sorted(inverses))
                derived = map(operator.itemgetter(1), sorted(derived))
                
                express_entity = express.entity(c.name, attributes, 
                    derived, inverses, constraints_by_type["EXPRESS_WHERE"], 
                    constraints_by_type["EXPRESS_UNIQUE"], subtypes, 
                    supertypes, is_abstract
                )
                             
                yield xmi_item(
                    "ENTITY", c.name, 
                    express_entity, c, children,
                    document=self,
                    supertypes=subtypes
                )
