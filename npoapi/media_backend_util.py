import logging
import os
from xml.dom import minidom

import pyxb

from npoapi.media_backend import MediaBackend
from npoapi.xml import media, mediaupdate, poms
from npoapi.xml.mediaupdate import segmentUpdateType


class MediaBackendUtil(object):
    """
    Utilities for dealing with 'update' objects required by the NPO Backend API
    """
    __author__ = "Michiel Meeuwissen"
    logger = logging.getLogger("MediaBackendUtil")


    @staticmethod
    def main_title(object: mediaupdate.mediaUpdateType, string: str = None):
        """Gets/sets main title"""
        return MediaBackendUtil.title(object, media.textualTypeEnum.MAIN, string)

    @staticmethod
    def main_description(object: mediaupdate.mediaUpdateType, string: str = None):
        """Gets/set main description"""
        return \
            MediaBackendUtil.description(object, media.textualTypeEnum.MAIN, string)


    @staticmethod
    def title(object: mediaupdate.mediaUpdateType, textualType, string: str = None):
        """Gets the title with certain textual type from media update type.
        Optionally, it can also be set
        """
        if type(textualType) is str:
            textualType  = getattr(media.textualTypeEnum, textualType)

        if string:
            title = mediaupdate.titleUpdateType(MediaBackendUtil.strip_tags(string))
            title.type = textualType
            object.title.append(title)
            return title
        else:
            MediaBackendUtil.logger.debug("Not appending title because it is empty")
            if object.title:
                for t in object.title:
                    if t.type == textualType:
                        return t.value()
            return None

    @staticmethod
    def description(object: mediaupdate.mediaUpdateType, textualType, string: str):
        """Gets the description with certain textual type from media update type.
      Optionally, it can also be set
      """
        if type(textualType) is str:
            textualType = getattr(media.textualTypeEnum, textualType)
        if string:
            description = mediaupdate.descriptionUpdateType(MediaBackendUtil.strip_tags(string))
            description.type = textualType
            object.description.append(description)
            return description
        else:
            MediaBackendUtil.logger.debug("Not appending description because it is empty")
            if object.description:
                for d in object.description:
                    if d.type == textualType:
                        return d.value()
        return None


    @staticmethod
    def create_location(programUrl:str, **kwargs):
        # location_object = mediaupdate.locationUpdateType()
        location_object = mediaupdate.location()
        location_object.programUrl = programUrl
        return MediaBackendUtil.update_location(location_object, **kwargs)

    @staticmethod
    def update_location(
            location_object: mediaupdate.locationUpdateType,
            avFileFormat=None, bitrate=None, height=None, width=None, aspectratio=None,
            embargo=None
            ):
        programUrl = location_object.programUrl
        avAttributes = location_object.avAttributes
        if avAttributes is None:
            avAttributes = mediaupdate.avAtributeUpdateType()
            location_object.avAttributes = avAttributes

        if avFileFormat is None and avAttributes.avFileFormat is None:
            index = programUrl.rfind('.')
            ext = programUrl[index + 1:].upper()
            if hasattr(media.avFileFormatEnum, ext):
                avFileFormat = getattr(media.avFileFormatEnum, ext)
            else:
                avFileFormat = media.avFileFormatEnum.UNKNOWN

        if type(avFileFormat) is str:
            avFileFormat = getattr(media.avFileFormatEnum, avFileFormat)

        if embargo:
            location_object.publishStart = embargo['publish_start']
            location_object.publishStop = embargo['publish_stop']

        if avFileFormat:
            avAttributes.avFileFormat = avFileFormat
        if bitrate:
            location_object.avAttributes.bitrate = bitrate
        if height or width or aspectratio:
            location_object.avAttributes.videoAttributes = mediaupdate.videoAttributesUpdateType()
            location_object.avAttributes.videoAttributes.height = height
            location_object.avAttributes.videoAttributes.width = width
            location_object.avAttributes.videoAttributes.aspectRatio = getattr(media.aspectRatioEnum, aspectratio, None)

        return location_object


    @staticmethod
    def add_location(object: mediaupdate.mediaUpdateType, programUrl:str, **kwargs):
        if not object.locations:
            object.locations = pyxb.BIND()

        location = MediaBackendUtil.create_location(programUrl, **kwargs)
        object.locations.append(location)
        return location

    @staticmethod
    def get_location(object: mediaupdate.mediaUpdateType, programUrl:str) -> mediaupdate.locationUpdateType:
        if not object.locations:
            return None
        for loc in object.locations.location:
            if str(loc.programUrl) is str(programUrl):
                return loc
        return loc

    @staticmethod
    def add_or_update_location(object: mediaupdate.mediaUpdateType, programUrl: str,
                               **kwargs) -> mediaupdate.locationUpdateType:
        loc = MediaBackendUtil.get_location(object, programUrl)
        if loc:
            logging.debug("Found existing %s for %s", loc, programUrl)
            return MediaBackendUtil.update_location(loc, **kwargs)
        else:
            return MediaBackendUtil.add_location(object, programUrl, **kwargs)


    @staticmethod
    def create_image_from_file(image, **kwargs):
        if os.path.isfile(image):
            with open(image, "rb") as image_file:
                image_object = mediaupdate.image()
                image_object.imageData = mediaupdate.imageDataType()
                image_object.imageData.data = image_file.read()
                MediaBackendUtil.set_image_fields(image_object, **kwargs)
                return image_object
        return None

    @staticmethod
    def create_image_from_url(imageUrl: str, **kwargs):
        image_object = mediaupdate.image()

        if imageUrl.startswith("urn:"):
            image_object.urn = imageUrl
        else:
            image_object.imageLocation = mediaupdate.imageLocationType()
            image_object.imageLocation.url = imageUrl
        MediaBackendUtil.set_image_fields(image_object, **kwargs)
        return image_object

    @staticmethod
    def set_image_fields(image_object, image_type="PICTURE", title=None, description=None, highlighted=False, license="COPYRIGHTED", source=None, source_name=None, credits=None):
        if image_type is None:
            image_type = "PICTURE"
        image_object.type = image_type
        image_object.highlighted = highlighted
        if title:
            image_object.title = MediaBackendUtil.strip_tags(title)
        if description:
            image_object.description = MediaBackendUtil.strip_tags(description)
        if source:
            image_object.source = source
        if source_name:
            image_object.sourceName = source_name
        if license:
            image_object.license = license
        if credits:
            image_object.credits = credits


    @staticmethod
    def add_image(object: mediaupdate.mediaUpdateType, image: str, **kwargs):
        if not object.images:
            object.images = pyxb.BIND()

        new_image = MediaBackendUtil.create_image(image, **kwargs)
        object.images.append(new_image)
        return image


    @staticmethod
    def create_image(image: str, **kwargs):
        if type(image) == str and os.path.isfile(image):
            return MediaBackendUtil.create_image_from_file(image, **kwargs)
        else:
            return MediaBackendUtil.create_image_from_url(image, **kwargs)




    @staticmethod
    def member_of(object: mediaupdate.mediaUpdateType, group:str, position:int=None):
        memberOf = mediaupdate.memberRefUpdateType(group)
        memberOf.highlighted = False
        if position is not None:
            memberOf.position = position
        object.memberOf.append(memberOf)

    @staticmethod
    def descendants(client: MediaBackend, mid: str, batch: int = 200, target: list = None, log_progress: bool = False, log_indent="", episodes=True, segments=False, recurse_programs=False, limit:int = None) -> list:
        """Returns a list of minidom item -> mediaUpdate"""
        if target is None:
            target = []
        new_targets = []
        if log_progress:
            MediaBackendUtil.logger.info("%sGetting members of %s", log_indent, mid)
        members = client.members(mid, batch=batch, limit=limit, log_progress=log_progress, log_indent=log_indent)
        MediaBackendUtil.logger.debug("%s  -> found %s members", log_indent, str(len(members)))
        new_targets.extend(members)
        if episodes:
            if log_progress:
                MediaBackendUtil.logger.info("%sGetting episodes of %s", log_indent, mid)
            eps = client.episodes(mid, batch=batch,limit=limit - len(members) if limit else None,  log_progress=log_progress, log_indent=log_indent)
            MediaBackendUtil.logger.debug("%s  -> found %s episodes", log_indent, str(len(eps)))
            new_targets.extend(eps)
            #print(eps)

        if segments:
            update = minidom.parseString(client.get(mid)).documentElement
            updateType = update.localName
            is_program = updateType == "program"
            if is_program:
                program_segments = MediaBackendUtil.segments_as_members(update)
                new_targets.extend(program_segments)
                if log_progress:
                    MediaBackendUtil.logger.info("%sFound %s segments for %s", log_indent, len(program_segments), mid)
            else:
                MediaBackendUtil.logger.info("%sNot a program but %s (%s)", log_indent, updateType, mid)




        target.extend(new_targets)

        if not limit or len(target) < int(limit):
            for m in new_targets:
                updateElement = m.getElementsByTagName("mediaUpdate")[0]
                mid = updateElement.getAttribute("mid")
                xsiType = updateElement.getAttribute("xsi:type")
                is_group = xsiType == "groupUpdateType"
                if is_group or recurse_programs:
                    if log_progress:
                        MediaBackendUtil.logger.debug("%sRecursing in %s (group: %s)", log_indent, mid, str(is_group))
                    MediaBackendUtil.descendants(client, mid, batch, target, log_progress=log_progress, log_indent=log_indent + "   ", limit=limit, episodes=episodes and is_group, recurse_programs=recurse_programs, segments=segments)
                    if limit and len(target) > int(limit):
                        MediaBackendUtil.logger.info("limit reached")
                        break
                else:
                    if segments and xsiType == "programUpdateType":
                        program_segments = MediaBackendUtil.segments_as_members(updateElement)
                        target.extend(program_segments)
                        if log_progress:
                            if len(program_segments) > 0:
                                MediaBackendUtil.logger.info("%sFound %s segments for %s", log_indent, len(program_segments), mid)
                    MediaBackendUtil.logger.debug("%sNot recursing in %s (group: %s)", log_indent, mid, str(is_group))
        else:
            MediaBackendUtil.logger.info("Limit reached %s > %s", len(target), limit)

        return target


    @staticmethod
    def segments_as_members(program) -> list:
        if type(program) == str:
            program = minidom.parseString(program)
        segments = program.getElementsByTagName('segment')

        def segment_to_item(m):
            item = minidom.parseString('<item xmlns="urn:vpro:media:update:2009" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="memberUpdateType" />')
            m.tagName = "mediaUpdate"
            m.setAttributeNS("http://www.w3.org/2001/XMLSchema-instance", "xsi:type", "segmentUpdateType")
            #m.setAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            #m.setAttribute("xmlns", "urn:vpro:media:update:2009")
            item.documentElement.appendChild(m)
            return item

        return list(map(segment_to_item, segments))


    @staticmethod
    def iterate_objects(members):
        if type(members) == str:
            members = minidom.parseString(members)
        if type(members) == minidom.Document:
            members = members.getElementsByTagName('item')
        result = map(lambda m:
                     poms.CreateFromDOM(m.getElementsByTagName("mediaUpdate")[0], mediaupdate.Namespace), members)

        return result

    @staticmethod
    def toxml(update):
        "xsi:- xml are not working out of the box.."
        return MediaBackend.toxml(update)

    @staticmethod
    def parse(duration_in_ms: int):
        """Converts millis to hours, minutes, seconds, millis"""
        millis = duration_in_ms % 1000
        seconds = duration_in_ms / 1000
        hours = seconds // 3600
        seconds -= hours * 3600
        minutes = seconds // 60
        seconds -= minutes * 60
        return (hours, minutes, seconds, millis)

    @staticmethod
    def un_parse(hours, minutes, seconds, millis=0):
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis

    @staticmethod
    def format_duration(duration_in_ms: int):
        """ Format duration as a ISO_8601"""
        (hours, minutes, seconds, millis) = MediaBackendUtil.parse(duration_in_ms)
        if hours == 0 and minutes == 0 and millis == 0:
            return "P0DT%dS" % seconds
        else:
            return "P0DT%dH%dM%d.%03dS" % (hours, minutes, seconds, millis)

    @staticmethod
    def strip_tags(html:str) -> str:
        s = MLStripper()
        s.feed("<html>" + html + "</html>")
        return s.get_data()

    @staticmethod
    def mediatype(update):
        if type(update) == segmentUpdateType:
            return "SEGMENT"
        else:
            return update.type


from html.parser import HTMLParser
class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)
