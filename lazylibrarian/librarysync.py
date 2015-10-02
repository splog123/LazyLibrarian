#import glob
import lazylibrarian
from lazylibrarian import database
from lazylibrarian import importer
from lazylibrarian import logger
from lazylibrarian.gr import GoodReads
import os
import re
import shlex


def getList(st):
    my_splitter = shlex.shlex(st, posix=True)
    my_splitter.whitespace += ','
    my_splitter.whitespace_split = True
    return list(my_splitter)


def LibraryScan(dir=None):
    if not dir:
        if not lazylibrarian.DOWNLOAD_DIR:
            return
        else:
            dir = lazylibrarian.DOWNLOAD_DIR

    if not os.path.isdir(dir):
        logger.warn('Cannot find directory: %s. Not scanning' % dir.decode(lazylibrarian.SYS_ENCODING, 'replace'))
        return
	
    myDB = database.DBConnection()
    new_authors = []

    logger.info('Scanning ebook directory: %s' % dir.decode(lazylibrarian.SYS_ENCODING, 'replace'))

    book_list = []
    new_book_count = 0
    file_count = 0
    book_exists = False

    if (lazylibrarian.FULL_SCAN):
        books = myDB.select('select AuthorName, BookName from books where Status=?', [u'Open'])
        status = lazylibrarian.NOTFOUND_STATUS
        logger.info('Missing books will be marked as %s' % status)
        for book in books:
            for book_type in getList(lazylibrarian.EBOOK_TYPE):
                bookName = book['BookName']
                bookAuthor = book['AuthorName']
                #Default destination path, should be allowed change per config file.
                dest_path = lazylibrarian.EBOOK_DEST_FOLDER.replace('$Author', bookAuthor).replace('$Title', bookName)
                #dest_path = authorname+'/'+bookname
                global_name = lazylibrarian.EBOOK_DEST_FILE.replace('$Author', bookAuthor).replace('$Title', bookName)

                encoded_book_path = os.path.join(dir, dest_path, global_name + "." + book_type).encode(lazylibrarian.SYS_ENCODING)
                if os.path.isfile(encoded_book_path):
                    book_exists = True	
            if not book_exists:
                myDB.action('update books set Status=? where AuthorName=? and BookName=?', [status, bookAuthor, bookName])
                logger.info('Book %s updated as not found on disk' % encoded_book_path.decode(lazylibrarian.SYS_ENCODING, 'replace'))
                if bookAuthor not in new_authors:
                    new_authors.append(bookAuthor)

    latest_subdirectory = []
    for r, d, f in os.walk(dir):
        for directory in d[:]:
            if directory.startswith("."):
                d.remove(directory)
            #prevent magazine being scanned
            if directory.startswith("_"):
                d.remove(directory)
        for files in f:
            subdirectory = r.replace(dir, '')
            latest_subdirectory.append(subdirectory)
            logger.info("[%s] Now scanning subdirectory %s" % (dir.decode(lazylibrarian.SYS_ENCODING, 'replace'), subdirectory.decode(lazylibrarian.SYS_ENCODING, 'replace')))
            matchString = ''
            for char in lazylibrarian.EBOOK_DEST_FILE:
                matchString = matchString + '\\' + char
            #massage the EBOOK_DEST_FILE config parameter into something we can use with regular expression matching
            booktypes = ''
            count = -1;
            booktype_list = getList(lazylibrarian.EBOOK_TYPE)
            for book_type in booktype_list:
                count += 1
                if count == 0:
                    booktypes = book_type
                else:
                    booktypes = booktypes + '|' + book_type
            matchString = matchString.replace("\\$\\A\\u\\t\\h\\o\\r", "(?P<author>.*?)").replace("\\$\\T\\i\\t\\l\\e", "(?P<book>.*?)") + '\.[' + booktypes + ']'
            #pattern = re.compile(r'(?P<author>.*?)\s\-\s(?P<book>.*?)\.(?P<format>.*?)', re.VERBOSE)
            pattern = re.compile(matchString, re.VERBOSE)
            match = pattern.match(files)
            if match:
                author = match.group("author")
                book = match.group("book")
                #check if book is in database, and not marked as in library
                check_exist_book = myDB.action("SELECT * FROM books where AuthorName=? and BookName=? and Status!=?", [author, book, 'Open']).fetchone()
                if not check_exist_book:
                    check_exist_author = myDB.action("SELECT * FROM authors where AuthorName=?", [author]).fetchone()
                    if not check_exist_author and lazylibrarian.ADD_AUTHOR:
                        GR = GoodReads(author)
                        try:
                            author_gr = GR.find_author_id()
                        except:
                            continue
                        #only try to add if GR data matches found author data
                        if author_gr:
                            authorid = author_gr['authorid']
                            authorlink  = author_gr['authorlink']
                            pageIdx = authorlink.rfind('/')
                            authorlink  = authorlink[pageIdx + 1:]
                            #match_auth = authorid+"."+author.replace('. ','_')
                            #Original Line does not allow author match.
                            match_auth = author.replace('.', '_')
                            match_auth = match_auth.replace(' ', '_')
                            match_auth = match_auth.replace('__', '_')
                            match_auth = authorid + "." + match_auth
                            # Hopefully someone can come up with a more efficient way of doing this.
                            logger.debug(match_auth)
                            logger.debug(authorlink)
                            if match_auth == authorlink:
                                logger.info("Adding %s" % author)
                                try:
                                    importer.addAuthorToDB(author)
                                except:
                                    continue
                                check_exist_book = myDB.action("SELECT * FROM books where AuthorName=? and BookName=?", [author, book]).fetchone()
                                if check_exist_book:
                                    if author not in new_authors:
                                        new_authors.append(author)
                                    myDB.action('UPDATE books set Status=? where AuthorName=? and BookName=?', ['Open', author, book])
                                    new_book_count += 1
                            else:
                                logger.info("Unable to match %s in GoodReads database" % author)
							

                else:
                    if author not in new_authors:
                        new_authors.append(author)
                    myDB.action('UPDATE books set Status=? where AuthorName=? and BookName=?', ['Open', author, book])
                    new_book_count += 1
				
                file_count += 1
	
    logger.info("%s new/modified books found and added to the database" % new_book_count)
    logger.info('Updating %i authors' % len(new_authors))
    for auth in new_authors:
        havebooks = len(myDB.select('select BookName from Books where status=? and AuthorName=?', ['Open', auth]))
        myDB.action('UPDATE authors set HaveBooks=? where AuthorName=?', [havebooks, auth])
        totalbooks = len(myDB.select('select BookName from Books where status!=? and AuthorName=?', ['Ignored', auth]))
        myDB.action('UPDATE authors set UnignoredBooks=? where AuthorName=?', [totalbooks, auth])

	logger.info('Library scan complete')
