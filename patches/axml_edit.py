"""Minimal Android binary XML (AXML) reader/writer.

Only what the port needs: read the string pool, read start elements with their
attributes, drop one attribute and append child elements. Used for the packages
whose ``AndroidManifest.xml`` cannot be decoded to text (apktool ``-r``), where
the original binary file has to stay in place.

The writer rebuilds the file from the parsed chunks, so every chunk keeps its
own size field consistent and no absolute offset has to be fixed up: AXML chunks
are laid out sequentially and only the string pool stores offsets, relative to
its own chunk start.
"""
import struct

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_ELEMENT_TYPE = 0x0102

UTF8_FLAG = 1 << 8
TYPE_STRING = 0x03


def _decode_len(data, pos):
    first = data[pos]
    if first & 0x80:
        return ((first & 0x7F) << 8) | data[pos + 1], pos + 2
    return first, pos + 1


def _encode_len(value):
    if value > 0x7F:
        return bytes(((value >> 8) | 0x80, value & 0xFF))
    return bytes((value,))


def _decode_utf8(data, pos):
    _, pos = _decode_len(data, pos)
    length, pos = _decode_len(data, pos)
    raw = data[pos:pos + length]
    return raw.decode("utf-8"), pos + length + 1


def _decode_utf16(data, pos):
    length = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    raw = data[pos:pos + length * 2]
    return raw.decode("utf-16-le"), pos + length * 2 + 2


def _encode_utf8(text):
    raw = text.encode("utf-8")
    return _encode_len(len(text)) + _encode_len(len(raw)) + raw + b"\x00"


def _encode_utf16(text):
    raw = text.encode("utf-16-le")
    return struct.pack("<H", len(text)) + raw + b"\x00\x00"


class StringPool:
    def __init__(self, strings, utf8):
        self.strings = list(strings)
        self.utf8 = utf8

    @classmethod
    def parse(cls, chunk):
        (_, _, _) = struct.unpack_from("<HHI", chunk, 0)
        string_count, _, flags, strings_start, styles_start = struct.unpack_from(
            "<IIIII", chunk, 8)
        utf8 = bool(flags & UTF8_FLAG)
        offsets = struct.unpack_from("<%dI" % string_count, chunk, 28)
        decode = _decode_utf8 if utf8 else _decode_utf16
        strings = [decode(chunk, strings_start + off)[0] for off in offsets]
        return cls(strings, utf8)

    def index_of(self, text):
        return self.strings.index(text)

    def add(self, text):
        if text not in self.strings:
            self.strings.append(text)
        return self.strings.index(text)

    def build(self):
        encode = _encode_utf8 if self.utf8 else _encode_utf16
        blob = bytearray()
        offsets = []
        for text in self.strings:
            offsets.append(len(blob))
            blob += encode(text)
        # AXML pads the string data so the pool size stays a multiple of four.
        while len(blob) % 4:
            blob += b"\x00"
        strings_start = 28 + 4 * len(self.strings)
        size = strings_start + len(blob)
        flags = UTF8_FLAG if self.utf8 else 0
        head = struct.pack("<HHI", RES_STRING_POOL_TYPE, 28, size)
        head += struct.pack("<IIIII", len(self.strings), 0, flags, strings_start, 0)
        head += b"".join(struct.pack("<I", off) for off in offsets)
        return head + bytes(blob)


class StartElement:
    def __init__(self, name_index, attributes, line_number=0):
        # attributes: list of (ns, name, raw, size, res0, data_type, data)
        self.name_index = name_index
        self.attributes = list(attributes)
        self.line_number = line_number

    @classmethod
    def parse(cls, chunk):
        line_number = struct.unpack_from("<I", chunk, 8)[0]
        _, name = struct.unpack_from("<II", chunk, 16)
        attr_start, attr_size, attr_count = struct.unpack_from("<HHH", chunk, 24)
        base = 16 + attr_start
        attributes = []
        for i in range(attr_count):
            off = base + i * attr_size
            ns, aname, raw = struct.unpack_from("<III", chunk, off)
            size, res0, data_type = struct.unpack_from("<HBB", chunk, off + 12)
            data = struct.unpack_from("<I", chunk, off + 16)[0]
            attributes.append((ns, aname, raw, size, res0, data_type, data))
        return cls(name, attributes, line_number)

    def build(self):
        size = 36 + 20 * len(self.attributes)
        out = struct.pack("<HHI", RES_XML_START_ELEMENT_TYPE, 16, size)
        out += struct.pack("<II", self.line_number, 0xFFFFFFFF)
        out += struct.pack("<II", 0xFFFFFFFF, self.name_index)
        out += struct.pack("<HHHHHH", 20, 20, len(self.attributes), 0, 0, 0)
        for ns, aname, raw, size, res0, data_type, data in self.attributes:
            out += struct.pack("<III", ns, aname, raw)
            out += struct.pack("<HBB", size, res0, data_type)
            out += struct.pack("<I", data)
        return out

    @staticmethod
    def string_attribute(ns_index, name_index, value_index):
        return (ns_index, name_index, value_index, 8, 0, TYPE_STRING, value_index)


def build_end_element(name_index, line_number=0):
    out = struct.pack("<HHI", 0x0103, 16, 24)
    out += struct.pack("<II", line_number, 0xFFFFFFFF)
    out += struct.pack("<II", 0xFFFFFFFF, name_index)
    return out


class BinaryXml:
    def __init__(self, data):
        self.raw = data
        if struct.unpack_from("<H", data, 0)[0] != RES_XML_TYPE:
            raise ValueError("not a binary AndroidManifest.xml")
        self.header_size = struct.unpack_from("<H", data, 2)[0]
        total = struct.unpack_from("<I", data, 4)[0]
        chunks = []
        offset = self.header_size
        while offset < total:
            (ctype, _, csize) = struct.unpack_from("<HHI", data, offset)
            chunks.append((ctype, data[offset:offset + csize]))
            offset += csize
        self.pool = None
        self.resource_map = None
        self.entries = []
        for ctype, chunk in chunks:
            if ctype == RES_STRING_POOL_TYPE:
                self.pool = StringPool.parse(chunk)
            elif ctype == RES_XML_RESOURCE_MAP_TYPE:
                self.resource_map = chunk
            elif ctype == RES_XML_START_ELEMENT_TYPE:
                # Keep the parsed object so attribute edits survive a rebuild.
                self.entries.append((ctype, StartElement.parse(chunk)))
            else:
                self.entries.append((ctype, chunk))

    def element_name(self, element):
        return self.pool.strings[element.name_index]

    def attribute(self, element, name):
        index = self.pool.index_of(name)
        for ns, aname, raw, _, _, data_type, data in element.attributes:
            if aname == index:
                if data_type == TYPE_STRING:
                    return self.pool.strings[data]
                return data
        return None

    def drop_attribute(self, element, name):
        index = self.pool.index_of(name)
        kept = [a for a in element.attributes if a[1] != index]
        removed = len(element.attributes) - len(kept)
        element.attributes = kept
        return removed

    def find_start_elements(self, name):
        if name not in self.pool.strings:
            return []
        index = self.pool.index_of(name)
        found = []
        for position, (ctype, payload) in enumerate(self.entries):
            if ctype == RES_XML_START_ELEMENT_TYPE:
                if payload.name_index == index:
                    found.append((position, payload))
        return found

    def find_end_element_index(self, start_position):
        cursor = start_position + 1
        while cursor < len(self.entries):
            if self.entries[cursor][0] == 0x0103:
                return cursor
            cursor += 1
        raise ValueError("unbalanced elements in manifest")

    def insert_child_after(self, start_position, element):
        end_position = self.find_end_element_index(start_position)
        # find_end_element_index lands on the closing tag of the first child, so
        # the new sibling goes right after it - not before it, which would nest
        # the new element inside that child.
        at = end_position + 1
        self.entries.insert(
            at, (RES_XML_START_ELEMENT_TYPE, element))
        self.entries.insert(
            at + 1,
            (0x0103, build_end_element(element.name_index)))

    def find_matching_end(self, start_position):
        """Index of the END_ELEMENT closing the element at start_position."""
        depth = 0
        for index in range(start_position, len(self.entries)):
            kind = self.entries[index][0]
            if kind == RES_XML_START_ELEMENT_TYPE:
                depth += 1
            elif kind == 0x0103:
                depth -= 1
                if depth == 0:
                    return index
        raise ValueError("unbalanced elements in manifest")

    def drop_element(self, position):
        """Remove the element at `position` together with its closing chunk."""
        end = self.find_matching_end(position)
        del self.entries[position:end + 1]

    def append_children(self, start_position, elements):
        """Append already built element trees as the last children."""
        end_position = self.find_matching_end(start_position)
        chunks = []
        for element in elements:
            chunks.extend(element.to_chunks())
        self.entries[end_position:end_position] = chunks

    def insert_before(self, position, elements):
        """Insert element trees immediately before the chunk at position."""
        chunks = []
        for element in elements:
            chunks.extend(element.to_chunks())
        self.entries[position:position] = chunks

    def element(self, name, attributes=()):
        return ElementTree(self.pool.add(name), attributes)

    def ensure_resource_id(self, resource_id, attribute_name):
        """Ensure the resource map maps the attribute name to the given resource ID.

        The resource map is an array where the index corresponds to the string pool
        index and the value is the resource ID. When adding attributes like
        android:authorities (0x01010018) that were not in the original manifest,
        we must ensure the resource map is large enough and contains the correct
        mapping.

        Args:
            resource_id: The Android resource ID (e.g., 0x01010018 for authorities)
            attribute_name: The attribute name string (e.g., "authorities")
        """
        # Find the attribute name in the string pool
        try:
            attr_index = self.pool.strings.index(attribute_name)
        except ValueError:
            # Attribute name not in string pool yet, add it
            attr_index = self.pool.add(attribute_name)

        if self.resource_map is None:
            # Create a new resource map with enough entries
            num_ids = attr_index + 1
            size = 8 + 4 * num_ids
            self.resource_map = struct.pack("<HHI", RES_XML_RESOURCE_MAP_TYPE, 8, size)
            # Fill with 0 (no resource ID) for all entries except the target
            ids = [0] * num_ids
            ids[attr_index] = resource_id
            self.resource_map += b"".join(struct.pack("<I", rid) for rid in ids)
            return

        # Parse existing resource map
        ctype, hsize, csize = struct.unpack_from("<HHI", self.resource_map, 0)
        num_ids = (csize - 8) // 4
        ids = list(struct.unpack_from("<" + "I" * num_ids, self.resource_map, 8))

        # Extend the resource map if necessary
        if attr_index >= len(ids):
            ids.extend([0] * (attr_index + 1 - len(ids)))

        # Set the resource ID at the correct index
        ids[attr_index] = resource_id

        # Rebuild the resource map
        num_ids = len(ids)
        size = 8 + 4 * num_ids
        self.resource_map = struct.pack("<HHI", RES_XML_RESOURCE_MAP_TYPE, 8, size)
        self.resource_map += b"".join(struct.pack("<I", rid) for rid in ids)

    def build(self):
        body = self.pool.build()
        if self.resource_map is not None:
            body += self.resource_map
        for ctype, payload in self.entries:
            body += payload.build() if ctype == RES_XML_START_ELEMENT_TYPE else payload
        header = struct.pack("<HHI", RES_XML_TYPE, self.header_size,
                             self.header_size + len(body))
        return header + body


class ElementTree:
    """An element with nested children, flattened into AXML chunks on demand."""

    def __init__(self, name_index, attributes=()):
        self.name_index = name_index
        # Accept either a full (ns, name, raw, size, res0, type, data) tuple or
        # the short (ns, name, value) form for a plain string attribute.
        self.attributes = [attr if len(attr) == 7
                           else StartElement.string_attribute(*attr)
                           for attr in attributes]
        self.children = []

    def append(self, child):
        self.children.append(child)
        return child

    def to_chunks(self):
        element = StartElement(self.name_index, self.attributes)
        chunks = [(RES_XML_START_ELEMENT_TYPE, element)]
        for child in self.children:
            chunks.extend(child.to_chunks())
        chunks.append((0x0103, build_end_element(self.name_index)))
        return chunks


def android_uses_permission(pool, permission):
    """<uses-permission android:name="permission"/> as an AXML chunk pair."""
    android_ns = pool.index_of("http://schemas.android.com/apk/res/android")
    element = StartElement(
        pool.add("uses-permission"),
        [StartElement.string_attribute(
            android_ns, pool.add("name"), pool.add(permission))])
    return element
