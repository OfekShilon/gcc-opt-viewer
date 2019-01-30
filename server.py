# TODO: license
import html
import os
import urllib

from flask import Flask, render_template, Markup
import pygments.lexers
import pygments.styles
import pygments.formatters

from optrecord import TranslationUnit, Record, Expr, Stmt, SymtabNode

app = Flask(__name__)

def record_sort_key(record):
    if not record.count:
        return 0
    return -record.count.value

def iter_all_records(app):
    for tu in app.tus:
        for r in tu.iter_all_records():
            yield r

def get_summary_text(record):
    '''
    if record.kind == 'scope':
        if record.children:
            return get_summary_text(record.children[-1])
    '''
    return get_html_for_message(record)

def get_html_for_message(record):
    html_for_message = ''
    for item in record.message:
        if isinstance(item, str):
            html_for_message += html.escape(str(item))
        else:
            if isinstance(item, Expr):
                html_for_item = '<code>%s</code>' % html.escape(item.expr)
            elif isinstance(item, Stmt):
                html_for_item = '<code>%s</code>' % html.escape(item.stmt)
            elif isinstance(item, SymtabNode):
                html_for_item = '<code>%s</code>' % html.escape(item.node)
            else:
                raise TypeError('unknown message item: %r' % item)
            if item.location:
                html_for_item = ('<a href="%s">%s</a>'
                                 % (url_from_location (item.location), html_for_item))
            html_for_message += html_for_item

    if record.children:
        for child in record.children:
            for line in get_html_for_message(child).splitlines():
                html_for_message += '\n  ' + line
    return html_for_message

def url_from_location(loc):
    return '%s#line-%i' % (url_from_sourcefile(loc.file), loc.line)

def url_from_sourcefile(sourcefile):
    return '/sourcefile/%s' % sourcefile

class Function:
    def __init__(self, name, sourcefile, hotness, tu, peak_location):
        self.name = name
        self.sourcefile = sourcefile
        self.hotness = hotness
        self.tu = tu
        self.peak_location = peak_location

@app.route("/")
def index():
    # Gather all records
    records = list(iter_all_records(app))

    # Sort by highest-count down to lowest-count
    records = sorted(records, key=record_sort_key)

    for r in records:
        r.message_html = Markup(get_html_for_message(r))

    # Mapping of name to Function
    functions = {}
    for tu in app.tus:
        for r in tu.iter_all_records():
            if r.count:
                hotness = r.count.value
            else:
                hotness = 0
            funcname = r.function
            if not funcname:
                continue
            if r.location:
                sourcefile = r.location.file
            else:
                sourcefile = None
            if funcname not in functions:
                functions[funcname] = Function(funcname, sourcefile,
                                               hotness, tu.filename, r.location)
            else:
                f = functions[funcname]
                if not f.sourcefile:
                    f.sourcefile = sourcefile
                if f.hotness < hotness:
                    f.hotness = hotness
                if r.location:
                    if f.hotness < hotness or not f.peak_location:
                        f.peak_location = r.location

    return render_template('index.html',
                           records=records,
                           functions=sorted(list(functions.values()),
                                            key=lambda f: f.hotness,
                                            reverse=True),
                           tus = app.tus,
                           total_size = sum([tu.size for tu in app.tus]),
                           count_top_level = sum([len(tu.records) for tu in app.tus]),
                           count_all  = sum([tu.count_all_records() for tu in app.tus]),
                           url_from_location=url_from_location,
                           url_from_sourcefile=url_from_sourcefile)

@app.route("/all-tus")
def all_tus():
    return "tus: %r" % app.tus

@app.route("/pass/<passname>")
def pass_(passname):
    # Gather records from the given pass
    records = [r for r in iter_all_records(app)
               if r.pass_.name == passname]

    # Sort by highest-count down to lowest-count
    records = sorted(records, key=record_sort_key)

    return render_template('pass.html',
                           records=records,
                           passname=passname)

@app.route("/sourcefile/<sourcefile>")
def sourcefile(sourcefile):
    # FIXME: this allows arbitrary reading of files on this machine:
    with open(os.path.join(app.build_dir, sourcefile)) as f:
        code = f.read()

    style = pygments.styles.get_style_by_name('default')
    formatter = pygments.formatters.HtmlFormatter()
    lexer = pygments.lexers.guess_lexer_for_filename(sourcefile, code)

    # Use pygments to convert it all to HTML:
    code_as_html = pygments.highlight(code, lexer, formatter)

    if 0:
        print(code_as_html)
        print('*' * 76)
        print(repr(code_as_html))
        print('*' * 76)

    EXPECTED_START = '<div class="highlight"><pre>'
    assert code_as_html.startswith(EXPECTED_START)
    code_as_html = code_as_html[len(EXPECTED_START):-1]

    EXPECTED_END = '</pre></div>'
    assert code_as_html.endswith(EXPECTED_END)
    code_as_html = code_as_html[0:-len(EXPECTED_END)]

    html_lines = [Markup(line) for line in code_as_html.splitlines()]

    return render_template('sourcefile.html',
                           sourcefile=sourcefile,
                           lines=html_lines,
                           css = formatter.get_style_defs())

@app.route("/records")
def records():
    # Gather all records
    records = list(iter_all_records(app))

    # Sort by highest-count down to lowest-count
    records = sorted(records, key=record_sort_key)

    for r in records:
        r.message_html = Markup(get_html_for_message(r))

    return render_template('records.html',
                           records=records,
                           url_from_location=url_from_location)
