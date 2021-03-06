#!/usr/bin/env python
#a Imports
import re
import sys, inspect

#a Classes
#c c_dump
class c_dump(object):
    #b Static properties
    res = {}
    res["hex"]        = r"([0-9a-fA-f]+)"
    res["whitespace"] = r"(\s+)"
    res["uid"]        = r"([a-zA-Z_][a-zA-Z_0-9]*)"
    res["label_match"] = re.compile(r"%s%s<%s>:"%(res["hex"], res["whitespace"], res["uid"]))
    res["data_match"]  = re.compile(r"%s:%s%s.*"%(res["hex"], res["whitespace"], res["hex"]))
    res["data_label_match"]  = re.compile(r"#%s%s%s<%s>"%(res["whitespace"], res["hex"], res["whitespace"], res["uid"]))
    res["mif_label_match"]       = re.compile(r"#%s%s:%s:"%(res["whitespace"], res["hex"], res["uid"]))
    res["mif_data_match"]        = re.compile(r"%s:%s%s.*"%(res["hex"], res["whitespace"], res["hex"]))
    res["mif_data_label_match"]  = re.compile(r"#%s%s%s<%s>"%(res["whitespace"], res["hex"], res["whitespace"], res["uid"]))
    def __init__(self):
    #f __init__
        self.reset()
        pass
    #f reset
    def reset(self):
        self.labels = {}
        self.data   = {}
        pass
    #f load
    def load(self, f, base_address=0):
        self.reset()
        for l in f:
            label_match = self.res["label_match"].match(l)
            data_match  = self.res["data_match"].match(l)
            data_label_match  = self.res["data_label_match"].search(l)
            if label_match:
                self.add_label(label_match.group(3), int(label_match.group(1),16), base_address)
                pass
            if data_match:
                self.add_data(int(data_match.group(3),16), int(data_match.group(1),16), base_address)
                pass
            if data_label_match:
                self.add_label(data_label_match.group(4), int(data_label_match.group(2),16), base_address)
                pass
            pass
        pass
    #f load_mif
    def load_mif(self, f, base_address=0):
        self.reset()
        for l in f:
            label_match = self.res["mif_label_match"].match(l)
            data_match  = self.res["mif_data_match"].match(l)
            data_label_match  = self.res["mif_data_label_match"].search(l)
            if label_match:
                self.add_label(label_match.group(3), int(label_match.group(1),16), base_address)
                pass
            if data_match:
                self.add_data(int(data_match.group(3),16), 4*int(data_match.group(1),16), base_address)
                pass
            if data_label_match:
                self.add_label(data_label_match.group(4), int(data_label_match.group(2),16), base_address)
                pass
            pass
        pass
    #f add_label
    def add_label(self,label,address,base_address=0):
        self.labels[label] = address-base_address
        pass
    #f add_data
    def add_data(self,data,address,base_address=0):
        address = address-base_address
        offset = address&3
        address = address/4
        if offset!=0:
            self.add_data(data<<(8*offset),address*4,base_address=0)
            self.add_data(data>>(32-8*offset),address*4+4,base_address=0)
            return
        if address in self.data:
            data = data | self.data[address]
            pass
        self.data[address] = data
        pass
    #f resolve_label
    def resolve_label(self, label):
        if label not in self.labels:
            raise Exception("Unable to find label '%s'"%label)
        return self.labels[label]
    #f write_mif
    def write_mif(self, f):
        labels = self.labels.keys()
        labels.sort(cmp=lambda a,b:cmp(self.labels[a],self.labels[b]))

        label_addresses_map = {}
        for l in labels:
            la = self.labels[l]
            if la not in label_addresses_map: label_addresses_map[la]=[]
            label_addresses_map[la].append(l)
            pass

        for l in labels:
            print >>f, "#%8x:%s"%(self.labels[l],l)
            pass

        addresses = self.data.keys()
        addresses.sort()
        for a in addresses:
            r = "%08x: "%a
            r += "%08x" % self.data[a]
            if a in label_addresses_map:
                r += " #"
                for l in label_addresses_map[a]:
                    r += " %s"%l
                    pass
                pass
            print >>f, r
            pass
        pass
    #f All done
    pass
