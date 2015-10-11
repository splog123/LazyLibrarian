import sys, re
import thread, threading, time, Queue
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement

import lazylibrarian
from lazylibrarian import logger, formatter, database, SimpleCache

from lazylibrarian.common import USER_AGENT

import lib.fuzzywuzzy as fuzzywuzzy
from lib.fuzzywuzzy import fuzz, process

import lib.requests as requests

import time


class GoodReads:
    """Fetch book and author metadata from Goodreads.Element
    
    FIXME: The usrlib2 code had a caching function using SimpleCache.
    Put this back in using one of several cache plugins for Requests
    """


    def __init__(self, name=None):
        self.name = name.encode('utf-8')
        #self.type = type
        self.url = 'http://www.goodreads.com'
        self.timeout = 30
        self.params = {
            'key':  lazylibrarian.GR_API
        }


    def find_results(self, authorname=None, queue=None):
        threading.currentThread().name = "GR-SEARCH"
        resultlist = []
        api_hits = 0
        url = self.url + '/search.xml'
        self.params['q'] = authorname
        logger.info('Now searching GoodReads API with keyword: ' + authorname)

        try:
            try:
                r = requests.get(url, params=self.params, timeout=self.timeout)
            except Exception, e:
                logger.error("Error finding results: " + str(e))
            api_hits = api_hits + 1
            logger.debug('Searching for %s at: %s' % (authorname, r.url))
            try:
                rootxml = ElementTree.fromstring(r.content)
                resultxml = rootxml.getiterator('work')
            except Exception, e:
                logger.error("Error finding results: " + str(e))
            author_dict = []
            resultcount = 0
            for author in resultxml:
                bookdate = "0001-01-01"

                if (author.find('original_publication_year').text == None):
                    bookdate = "0000"
                else:
                    bookdate = author.find('original_publication_year').text

                authorNameResult = author.find('./best_book/author/name').text
                booksub = ""
                bookpub = ""
                booklang = "en"

                try:
                    bookimg = author.find('./best_book/image_url').text
                    if (bookimg == 'http://www.goodreads.com/assets/nocover/111x148.png'):
                        bookimg = 'images/nocover.png'
                except KeyError:
                    bookimg = 'images/nocover.png'
                except AttributeError:
                    bookimg = 'images/nocover.png'

                try:
                    bookrate = author.find('average_rating').text
                except KeyError:
                    bookrate = 0

                bookpages = '0'
                bookgenre = ''
                bookdesc = ''
                bookisbn = ''
                booklink = 'http://www.goodreads.com/book/show/'+author.find('./best_book/id').text

                if (author.find('./best_book/title').text == None):
                    bookTitle = ""
                else:
                    bookTitle = author.find('./best_book/title').text

                author_fuzz = fuzz.ratio(authorNameResult.lower(), authorname.lower())
                book_fuzz = fuzz.ratio(bookTitle.lower(), authorname.lower())
                try:
                    isbn_check = int(authorname[:-1])
                    if (len(str(isbn_check)) == 9) or (len(str(isbn_check)) == 12):
                        isbn_fuzz = int(100)
                    else:
                        isbn_fuzz = int(0)
                except:
                    isbn_fuzz = int(0)
                highest_fuzz = max(author_fuzz, book_fuzz, isbn_fuzz)

                resultlist.append({
                    'authorname': author.find('./best_book/author/name').text,
                    'bookid': author.find('./best_book/id').text,
                    'authorid' : author.find('./best_book/author/id').text,
                    'bookname': bookTitle.encode("ascii", "ignore"),
                    'booksub': booksub,
                    'bookisbn': bookisbn,
                    'bookpub': bookpub,
                    'bookdate': bookdate,
                    'booklang': booklang,
                    'booklink': booklink,
                    'bookrate': float(bookrate),
                    'bookimg': bookimg,
                    'bookpages': bookpages,
                    'bookgenre': bookgenre,
                    'bookdesc': bookdesc,
                    'author_fuzz': author_fuzz,
                    'book_fuzz': book_fuzz,
                    'isbn_fuzz': isbn_fuzz,
                    'highest_fuzz': highest_fuzz,
                    'num_reviews': float(bookrate)
                })

                resultcount = resultcount+1

        except requests.ConnectionError, err:
            if err.code == 404:
                logger.info('Received a 404 error when searching for author')
            if err.code == 403:
                logger.info('Access to api is denied: usage exceeded')
            else:
                logger.info('An unexpected error has occurred when searching for an author')

        logger.info('Found %s results with keyword: %s' % (resultcount, authorname))
        logger.info('The GoodReads API was hit %s times for keyword %s' % (str(api_hits), authorname))

        queue.put(resultlist)


    def find_author_id(self):

        url = self.url + '/api/author_url/' + self.name
        self.params['q'] = None
        logger.debug("Searching for author with name: %s" % self.name)

        try:
            r = requests.get(url, params=self.params, timeout=self.timeout)
        except Exception, e:
            logger.error("Error finding results: " + str(e))
        logger.debug('*** Author URL: %s' % r.url)
        try:
            rootxml = ElementTree.fromstring(r.content)
            resultxml = rootxml.getiterator('author')
        except Exception, e:
            logger.error("Error fetching authorid: " + str(e) + str(r.url))

        authorlist = []

        if not len(rootxml):
            logger.info('No authors found with name: %s' % self.name)
            return authorlist
        else:
            for author in resultxml:
                authorid = author.attrib.get("id")
                authorname = author[0].text
                logger.info('Found author: %s with GoodReads-id: %s' % (authorname, authorid))

            authorlist = self.get_author_info(authorid, authorname)

        return authorlist


    def get_author_info(self, authorid=None, authorname=None, refresh=False):

        url = self.url + '/author/show/' + authorid + '.xml'
        self.params['q'] = None
        try:
            r = requests.get(url, params=self.params, timeout=self.timeout)
        except Exception, e:
            logger.error("Error finding results: " + str(e))
        logger.debug('*** Author show URL: %s' % r.url)
        try:
            rootxml = ElementTree.fromstring(r.content)
            resultxml = rootxml.find('author')
        except Exception, e:
            logger.error("Error fetching author ID: " + str(e))

        author_dict = {}
        if not len(rootxml):
            logger.info('No author found with ID: ' + authorid)
        else:
            logger.info("[%s] Processing info for authorID: %s" % (authorname, authorid))
            author_dict = {
                'authorid':   resultxml[0].text,
                'authorlink':   resultxml.find('link').text,
                'authorimg':  resultxml.find('image_url').text,
                'authorborn':   resultxml.find('born_at').text,
                'authordeath':  resultxml.find('died_at').text,
                'totalbooks':   resultxml.find('works_count').text
            }
        return author_dict


    def get_author_books(self, authorid=None, authorname=None, refresh=False):

        api_hits = 0
        url = self.url + '/author/list/' + authorid + '.xml'
        self.params['q'] = None

        myDB = database.DBConnection()
        controlValueDict = {"AuthorID": authorid}
        newValueDict = {"Status": "Loading"}
        myDB.upsert("authors", newValueDict, controlValueDict)

        try:
            r = requests.get(url, params=self.params, timeout=self.timeout)
        except Exception, e:
            logger.error("Error finding results: " + str(e))
        logger.debug('*** Author list URL: %s' % r.url)
        try:
            rootxml = ElementTree.fromstring(r.content)
            resultxml = rootxml.getiterator('book')
        except Exception, e:
            logger.error("Error fetching author info: " + str(e))

        api_hits = api_hits + 1
        books_dict = []

        if not len(rootxml):
            logger.info('[%s] No books found for author with ID: %s' % (authorname, authorid))
        else:
            logger.info("[%s] Now processing books with GoodReads API" % authorname)

            resultsCount = 0
            removedResults = 0
            ignored = 0
            added_count = 0
            updated_count = 0
            book_ignore_count = 0
            total_count = 0
            logger.debug(u'url ' + r.url)
            authorNameResult = rootxml.find('./author/name').text
            logger.debug(u"author name " + authorNameResult)
            loopCount = 1;

            while (len(resultxml)):

                for book in resultxml:
                    total_count = total_count + 1

                    if (book.find('publication_year').text == None):
                        pubyear = "0000"
                    else:
                        pubyear = book.find('publication_year').text

                    try:
                        bookimg = book.find('image_url').text
                        if (bookimg == 'http://www.goodreads.com/assets/nocover/111x148.png'):
                            bookimg = 'images/nocover.png'
                    except KeyError:
                        bookimg = 'images/nocover.png'
                    except AttributeError:
                        bookimg = 'images/nocover.png'

                    bookLanguage = "Unknown"

                    try:
                        time.sleep(1) #sleep 1 second to respect goodreads api terms

                        #FIXME: Switch to search by id.
                        #       Who cares if the book doesn't have an ISBN?
                        #FIXME: This next chunk is duplicated. Use find_book()
                        if (book.find('isbn13').text is not None):
                            book_url = 'http://www.goodreads.com/book/isbn'
                            try:
                                r2 = requests.get(book_url, params={'key':lazylibrarian.GR_API, 'isbn':book.find('isbn13').text}, timeout=self.timeout)
                            except Exception, e:
                                logger.error("Error finding results: " + str(e))
                            logger.debug('*** Book URL: ' + r2.url)
                            try:
                                book_rootxml = ElementTree.fromstring(r2.content)
                                bookLanguage = book_rootxml.find('./book/language_code').text
                            except Exception, e:
                                logger.error("Error fetching book info: " + str(e))
                            logger.debug(u"language: " + str(bookLanguage))
                        else:
                            logger.debug("No ISBN provided, skipping")
                            continue

                    except Exception, e:
                        logger.debug(u"An error has occured: " + str(e))

                    if not bookLanguage:
                        bookLanguage = "Unknown"
                    valid_langs = ([valid_lang.strip() for valid_lang in lazylibrarian.IMP_PREFLANG.split(',')])
                    if bookLanguage not in valid_langs:
                        logger.debug('Skipped a book with language %s' % bookLanguage)
                        ignored = ignored + 1
                        continue

                    bookname = book.find('title').text
                    bookid = book.find('id').text
                    bookdesc = book.find('description').text
                    bookisbn = book.find('isbn').text
                    bookpub = book.find('publisher').text
                    booklink = book.find('link').text
                    bookrate = float(book.find('average_rating').text)
                    bookpages = book.find('num_pages').text

                    result = re.search(r"\(([\S\s]+)\, #(\d+)|\(([\S\s]+) #(\d+)", bookname)
                    if result:
                        if result.group(1) == None:
                            series = result.group(3)
                            seriesOrder = result.group(4)
                        else:
                            series = result.group(1)
                            seriesOrder = result.group(2)
                    else:
                        series = None
                        seriesOrder = None

                    find_book_status = myDB.select("SELECT * FROM books WHERE BookID = '%s'" % bookid)
                    if find_book_status:
                        for resulted in find_book_status:
                            book_status = resulted['Status']
                    else:
                        book_status = "Skipped"

                    if not (re.match('[^\w-]', bookname)): #remove books with bad caracters in title
                        if book_status != "Ignored":
                            controlValueDict = {"BookID": bookid}
                            newValueDict = {
                                "AuthorName":   authorNameResult,
                                "AuthorID":     authorid,
                                "AuthorLink":   None,
                                "BookName":     bookname,
                                "BookSub":      None,
                                "BookDesc":     bookdesc,
                                "BookIsbn":     bookisbn,
                                "BookPub":      bookpub,
                                "BookGenre":    None,
                                "BookImg":      bookimg,
                                "BookLink":     booklink,
                                "BookRate":     bookrate,
                                "BookPages":    bookpages,
                                "BookDate":     pubyear,
                                "BookLang":     bookLanguage,
                                "Status":       book_status,
                                "BookAdded":    formatter.today(),
                                "Series":       series,
                                "SeriesOrder":  seriesOrder
                            }

                            resultsCount = resultsCount + 1

                            myDB.upsert("books", newValueDict, controlValueDict)
                            logger.debug(u"book found " + book.find('title').text + " " + pubyear)
                            if not find_book_status:
                                logger.info("[%s] Added book: %s" % (authorname, bookname))
                                added_count = added_count + 1
                            else:
                                logger.info("[%s] Updated book: %s" % (authorname, bookname))
                                updated_count = updated_count + 1
                        else:
                            book_ignore_count = book_ignore_count + 1
                    else:
                        removedResults = removedResults + 1

                loopCount = loopCount + 1
                url1 = self.url + '/author/list/' + authorid + '.xml?'
                self.params['q'] = None
                self.params['page'] = str(loopCount)

                try:
                    r1 = requests.get(url1, params=self.params, timeout=self.timeout)
                except Exception, e:
                    logger.error("Error finding results: " + str(e))				
                logger.debug('*** Author List URL: %s' % r1.url)
                try:
                    rootxml = ElementTree.fromstring(r1.content)
                    resultxml = rootxml.getiterator('book')
                except Exception, e:
                    logger.error("Error fetching author info: " + str(e))

                api_hits = api_hits + 1

        logger.info('[%s] The GoodReads API was hit %s times to populate book list' % (authorname, str(api_hits)))

        lastbook = myDB.action("SELECT BookName, BookLink, BookDate from books WHERE AuthorID='%s' AND Status != 'Ignored' order by BookDate DESC" % authorid).fetchone()
        if lastbook:
            lastbookname = lastbook['BookName']
            lastbooklink = lastbook['BookLink']
            lastbookdate = lastbook['BookDate']
        else:
            lastbookname = None
            lastbooklink = None
            lastbookdate = None

        unignoredbooks = myDB.select("SELECT COUNT(BookName) as unignored FROM books WHERE AuthorID='%s' AND Status != 'Ignored'" % authorid)
        bookCount = myDB.select("SELECT COUNT(BookName) as counter FROM books WHERE AuthorID='%s'" % authorid)   

        controlValueDict = {"AuthorID": authorid}
        newValueDict = {
                        "Status": "Active",
                        "TotalBooks": bookCount[0]['counter'],
                        "UnignoredBooks": unignoredbooks[0]['unignored'],
                        "LastBook": lastbookname,
                        "LastLink": lastbooklink,
                        "LastDate": lastbookdate
        }
        myDB.upsert("authors", newValueDict, controlValueDict)

        #This is here because GoodReads sometimes has several entries with the same BookID!
        modified_count = added_count + updated_count

        logger.debug("Found %s total books for author" % total_count)
        logger.debug("Removed %s bad language results for author" % ignored)
        logger.debug("Removed %s bad character results for author" % removedResults)
        logger.debug("Ignored %s books by author marked as Ignored" % book_ignore_count)
        logger.debug("Imported/Updated %s books for author" % modified_count)
        if refresh:
            logger.info("[%s] Book processing complete: Added %s books / Updated %s books" % (authorname, str(added_count), str(updated_count)))
        else:
            logger.info("[%s] Book processing complete: Added %s books to the database" % (authorname, str(added_count)))
        return books_dict


    def find_book(self, bookid=None, queue=None):
        threading.currentThread().name = "GR-ADD-BOOK"
        myDB = database.DBConnection()

        url = self.url + '/book/show/' + bookid
        self.params['q'] = None

        try:
            r = requests.get(url, params=self.params, timeout=self.timeout)
        except Exception, e:
            logger.error("Error finding results: " + str(e))
        logger.debug('*** Book show URL: %s' % r.url)
        try:
            rootxml = ElementTree.fromstring(r.content)
            bookLanguage = rootxml.find('./book/language_code').text
        except Exception, e:
            logger.error("Error fetching book info: " + str(e))

        if not bookLanguage:
            bookLanguage = "Unknown"
        valid_langs = ([valid_lang.strip() for valid_lang in lazylibrarian.IMP_PREFLANG.split(',')])
        if bookLanguage not in valid_langs:
            logger.debug('Skipped a book with language %s' % bookLanguage)

        if (rootxml.find('./book/publication_year').text == None):
            bookdate = "0000"
        else:
            bookdate = rootxml.find('./book/publication_year').text

        try:
            bookimg = rootxml.find('./book/img_url').text
            if (bookimg == 'http://www.goodreads.com/assets/nocover/111x148.png'):
                bookimg = 'images/nocover.png'
        except KeyError:
            bookimg = 'images/nocover.png'
        except AttributeError:
            bookimg = 'images/nocover.png'

        authorname = rootxml.find('./book/authors/author/name').text
        bookname = rootxml.find('./book/title').text
        bookdesc = rootxml.find('./book/description').text
        bookisbn = rootxml.find('./book/isbn').text
        bookpub = rootxml.find('./book/publisher').text
        booklink = rootxml.find('./book/link').text
        bookrate = float(rootxml.find('./book/average_rating').text)
        bookpages = rootxml.find('.book/num_pages').text

        name = authorname
        GR = GoodReads(name)
        author = GR.find_author_id()
        if author:
            AuthorID = author['authorid']

        controlValueDict = {"BookID": bookid}
        newValueDict = {
            "AuthorName":   authorname,
            "AuthorID":     AuthorID,
            "AuthorLink":   None,
            "BookName":     bookname,
            "BookSub":      None,
            "BookDesc":     bookdesc,
            "BookIsbn":     bookisbn,
            "BookPub":      bookpub,
            "BookGenre":    None,
            "BookImg":      bookimg,
            "BookLink":     booklink,
            "BookRate":     bookrate,
            "BookPages":    bookpages,
            "BookDate":     bookdate,
            "BookLang":     bookLanguage,
            "Status":       "Wanted",
            "BookAdded":    formatter.today()
        }

        myDB.upsert("books", newValueDict, controlValueDict)
        logger.info("%s added to the books database" % bookname)
