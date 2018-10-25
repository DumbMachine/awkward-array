#!/usr/bin/env python

# Copyright (c) 2018, DIANA-HEP
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import codecs

import awkward.util
import awkward.array.jagged
import awkward.array.objects

class StringMethods(object):
    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if method != "__call__":
            raise NotImplemented

        if ufunc is awkward.util.numpy.equal or ufunc is awkward.util.numpy.not_equal:
            if len(inputs) < 2:
                raise ValueError("invalid number of arguments")
            left, right = inputs[0], inputs[1]

            if isinstance(left, (str, bytes)):
                left = StringArray.fromstr(len(right), left)
            elif isinstance(left, awkward.util.numpy.ndarray) and (left.dtype.kind == "U" or left.dtype.kind == "S"):
                left = StringArray.fromnumpy(left)
            elif isinstance(left, awkward.util.numpy.ndarray) and left.dtype == awkward.util.numpy.dtype(object):
                left = StringArray.fromiter(left)
            elif not isinstance(left, StringMethods):
                return awkward.util.numpy.zeros(len(right), dtype=awkward.util.BOOLTYPE)

            if isinstance(right, (str, bytes)):
                right = StringArray.fromstr(len(left), right)
            elif isinstance(right, awkward.util.numpy.ndarray) and (right.dtype.kind == "U" or right.dtype.kind == "S"):
                right = StringArray.fromnumpy(right)
            elif isinstance(right, awkward.util.numpy.ndarray) and right.dtype == awkward.util.numpy.dtype(object):
                right = StringArray.fromiter(right)
            elif not isinstance(right, StringMethods):
                return awkward.util.numpy.zeros(len(left), dtype=awkward.util.BOOLTYPE)

            left = awkward.array.jagged.JaggedArray(left._starts, left._stops, left._content)
            right = awkward.array.jagged.JaggedArray(right._starts, right._stops, right._content)

            maybeequal = (left.counts == right.counts)

            leftmask = left[maybeequal]
            rightmask = right[maybeequal]
            reallyequal = (leftmask == rightmask).count_nonzero() == leftmask.counts()

            out = awkward.util.numpy.zeros(len(left), dtype=awkward.util.BOOLTYPE)
            out[maybeequal] = reallyequal

            if ufunc is awkward.util.numpy.equal:
                return out
            else:
                return awkward.util.numpy.logical_not(out)

        else:
            return super(StringMethods, self).__array_ufunc__(ufunc, method, *inputs, **kwargs)

def tostring(x, decoder):
    if decoder is None:
        return x.tostring()
    else:
        return decoder(x, errors="replace")[0]

class StringArray(StringMethods, awkward.array.objects.ObjectArray):
    def __init__(self, starts, stops, content, encoding="utf-8"):
        self._content = awkward.array.jagged.ByteJaggedArray(starts, stops, content, awkward.util.CHARTYPE)
        self._generator = tostring
        self._kwargs = {}
        self.encoding = encoding

    @classmethod
    def fromstr(cls, length, string, encoding="utf-8"):
        if encoding is not None:
            encoder = codecs.getencoder(encoding)
            string = encoder(string, errors="replace")[0]
        content = awkward.util.numpy.empty(length * len(string), dtype=awkward.util.CHARTYPE)
        for i, x in string:
            content[0::length] = ord(x)
        counts = awkward.util.numpy.empty(length, dtype=awkward.util.INDEXTYPE)
        counts[:] = length
        return cls.fromcounts(counts, content, encoding)

    @classmethod
    def fromnumpy(cls, array):
        if array.dtype.kind == "S":
            encoding = None
        elif array.dtype.kind == "U":
            encoding = "utf-32le"
        else:
            raise TypeError("not a string array")

        starts = awkward.util.numpy.arange(                   0,  len(array)      * array.dtype.itemsize, array.dtype.itemsize)
        stops  = awkward.util.numpy.arange(array.dtype.itemsize, (len(array) + 1) * array.dtype.itemsize, array.dtype.itemsize)
        content = array.view(awkward.util.CHARTYPE)

        shorter = awkward.util.numpy.ones(len(array), dtype=awkward.util.BOOLTYPE)
        if array.dtype.kind == "S":
            for checkat in range(array.dtype.itemsize - 1, -1, -1):
                shorter &= (content[checkat::array.dtype.itemsize] == 0)
                stops[shorter] -= 1
                if not shorter.any():
                    break

        elif array.dtype.kind == "U":
            content2 = content.view(awkward.util.numpy.uint32)
            itemsize2 = array.dtype.itemsize >> 2                 # itemsize // 4
            for checkat in range(itemsize2 - 1, -1, -1):
                shorter &= (content2[checkat::itemsize2] == 0)    # all four bytes are zero
                stops[shorter] -= 4
                if not shorter.any():
                    break

        out = cls.__new__(cls)
        out._content = awkward.array.jagged.ByteJaggedArray(starts, stops, content, awkward.util.CHARTYPE)
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out
        
    @classmethod
    def fromiter(cls, iterable, encoding="utf-8"):
        if encoding is None:
            encoded = iterable
        else:
            encoder = codecs.getencoder(encoding)
            encoded = [encoder(x, errors="replace")[0] for x in iterable]
        counts = [len(x) for x in encoded]
        content = awkward.util.numpy.empty(sum(counts), dtype=awkward.util.CHARTYPE)
        return cls.fromcounts(counts, content, encoding)

    @classmethod
    def fromoffsets(cls, offsets, content, encoding="utf-8"):
        out = cls.__new__(cls)
        out._content = awkward.array.jagged.ByteJaggedArray.fromoffsets(offsets, content, awkward.util.CHARTYPE)
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out

    @classmethod
    def fromcounts(cls, counts, content, encoding="utf-8"):
        out = cls.__new__(cls)
        out._content = awkward.array.jagged.ByteJaggedArray.fromcounts(counts, content, awkward.util.CHARTYPE)
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out

    @classmethod
    def fromparents(cls, parents, content, encoding="utf-8"):
        out = cls.__new__(cls)
        out._content = awkward.array.jagged.ByteJaggedArray.fromparents(parents, content, awkward.util.CHARTYPE)
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out

    @classmethod
    def fromuniques(cls, uniques, content, encoding="utf-8"):
        out = cls.__new__(cls)
        out._content = awkward.array.jagged.ByteJaggedArray.fromuniques(uniques, content, awkward.util.CHARTYPE)
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out

    @classmethod
    def fromjagged(cls, jagged, encoding="utf-8"):
        if jagged.content.type.to != awkward.util.CHARTYPE:
            raise TypeError("jagged array must have CHARTYPE ({0})".format(str(awkward.util.CHARTYPE)))
        out = cls.__new__(cls)
        out._content = jagged
        out._generator = tostring
        out._kwargs = {}
        out.encoding = encoding
        return out

    # def copy(self, content=None, generator=None, args=None, kwargs=None):
    #     out = self.__class__.__new__(self.__class__)
    #     out._content = self._content
    #     out._generator = self._generator
    #     out._args = self._args
    #     out._kwargs = self._kwargs
    #     if content is not None:
    #         out.content = content
    #     if generator is not None:
    #         out.generator = generator
    #     if args is not None:
    #         out.args = args
    #     if kwargs is not None:
    #         out.kwargs = kwargs
    #     return out

    # def deepcopy(self, content=None, generator=None, args=None, kwargs=None):
    #     out = self.copy(content=content, generator=generator, args=args, kwargs=kwargs)
    #     out._content = awkward.util.deepcopy(out._content)
    #     return out

    # def empty_like(self, **overrides):
    #     mine = {}
    #     mine["generator"] = overrides.pop("generator", self._generator)
    #     mine["args"] = overrides.pop("args", self._args)
    #     mine["kwargs"] = overrides.pop("kwargs", self._kwargs)
    #     if isinstance(self._content, awkward.util.numpy.ndarray):
    #         return self.copy(content=awkward.util.numpy.empty_like(self._content), **mine)
    #     else:
    #         return self.copy(content=self._content.empty_like(**overrides), **mine)

    # def zeros_like(self, **overrides):
    #     mine = {}
    #     mine["generator"] = overrides.pop("generator", self._generator)
    #     mine["args"] = overrides.pop("args", self._args)
    #     mine["kwargs"] = overrides.pop("kwargs", self._kwargs)
    #     if isinstance(self._content, awkward.util.numpy.ndarray):
    #         return self.copy(content=awkward.util.numpy.zeros_like(self._content), **mine)
    #     else:
    #         return self.copy(content=self._content.zeros_like(**overrides), **mine)

    # def ones_like(self, **overrides):
    #     mine = {}
    #     mine["generator"] = overrides.pop("generator", self._generator)
    #     mine["args"] = overrides.pop("args", self._args)
    #     mine["kwargs"] = overrides.pop("kwargs", self._kwargs)
    #     if isinstance(self._content, awkward.util.numpy.ndarray):
    #         return self.copy(content=awkward.util.numpy.ones_like(self._content), **mine)
    #     else:
    #         return self.copy(content=self._content.ones_like(**overrides), **mine)

    def __awkward_persist__(self, ident, fill, **kwargs):
        self._valid()
        n = self.__class__.__name__
        if awkward.array.jagged.offsetsaliased(self.starts, self.stops) and len(self.starts) > 0 and self.starts[0] == 0:
            return {"id": ident,
                    "call": ["awkward", n, "fromcounts"],
                    "args": [fill(self.counts, n + ".counts", **kwargs),
                             fill(self.content, n + ".content", **kwargs),
                             self._encoding]}
        else:
            return {"id": ident,
                    "call": ["awkward", n],
                    "args": [fill(self.starts, n + ".starts", **kwargs),
                             fill(self.stops, n + ".stops", **kwargs),
                             fill(self.content, n + ".content", **kwargs),
                             self._encoding]}

    @property
    def starts(self):
        return self._content.starts

    @starts.setter
    def starts(self, value):
        self._content.starts = value

    @property
    def stops(self):
        return self._content.stops

    @stops.setter
    def stops(self, value):
        self._content.stops = value

    @property
    def content(self):
        return self._content.content

    @content.setter
    def content(self, value):
        self._content.content = value

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return {}

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        if value is None:
            decodefcn = None
        else:
            decodefcn = codecs.getdecoder(value)
        self._encoding = value
        self._args = (decodefcn,)

    @property
    def offsets(self):
        return self._content.offsets

    @property
    def counts(self):
        return self._content.counts

    @property
    def parents(self):
        return self._content.parents

    @property
    def index(self):
        return self._content.index

