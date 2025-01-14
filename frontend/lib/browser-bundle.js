// Utility functions (from util.js)
(function(global) {
    global.util = {
        inherits: function(ctor, superCtor) {
            ctor.super_ = superCtor;
            ctor.prototype = Object.create(superCtor.prototype, {
                constructor: {
                    value: ctor,
                    enumerable: false,
                    writable: true,
                    configurable: true
                }
            });
        },
        isRegExp: function(obj) {
            return Object.prototype.toString.call(obj) === '[object RegExp]';
        }
    };
})(typeof window !== 'undefined' ? window : this);

// balanced-match
(function(global) {
    function balanced(a, b, str) {
        if (a instanceof RegExp) a = maybeMatch(a, str);
        if (b instanceof RegExp) b = maybeMatch(b, str);

        var r = range(a, b, str);

        return r && {
            start: r[0],
            end: r[1],
            pre: str.slice(0, r[0]),
            body: str.slice(r[0] + a.length, r[1]),
            post: str.slice(r[1] + b.length)
        };
    }

    function maybeMatch(reg, str) {
        var m = str.match(reg);
        return m ? m[0] : null;
    }

    balanced.range = range;

    function range(a, b, str) {
        var begs, beg, left, right, result;
        var ai = str.indexOf(a);
        var bi = str.indexOf(b, ai + 1);
        var i = ai;

        if (ai >= 0 && bi > 0) {
            if(a===b) {
                return [ai, bi];
            }
            begs = [];
            left = str.length;

            while (i >= 0 && !result) {
                if (i == ai) {
                    begs.push(i);
                    ai = str.indexOf(a, i + 1);
                } else if (begs.length == 1) {
                    result = [ begs.pop(), bi ];
                } else {
                    beg = begs.pop();
                    if (beg < left) {
                        left = beg;
                        right = bi;
                    }

                    bi = str.indexOf(b, i + 1);
                }

                i = ai < bi && ai >= 0 ? ai : bi;
            }

            if (begs.length) {
                result = [ left, right ];
            }
        }

        return result;
    }

    global.balancedMatch = balanced;
})(typeof window !== 'undefined' ? window : this);

// concat-map
(function(global) {
    function concatMap(xs, fn) {
        var res = [];
        for (var i = 0; i < xs.length; i++) {
            var x = fn(xs[i], i);
            if (Array.isArray(x)) res.push.apply(res, x);
            else res.push(x);
        }
        return res;
    }
    global.concatMap = concatMap;
})(typeof window !== 'undefined' ? window : this);

// brace-expansion
(function(global) {
    var concatMap = global.concatMap;
    var balancedMatch = global.balancedMatch;

    var escSlash = '\0SLASH' + Math.random() + '\0';
    var escOpen = '\0OPEN' + Math.random() + '\0';
    var escClose = '\0CLOSE' + Math.random() + '\0';
    var escComma = '\0COMMA' + Math.random() + '\0';
    var escPeriod = '\0PERIOD' + Math.random() + '\0';

    function escape(str) {
        return str.split('\\\\').join(escSlash)
            .split('\\{').join(escOpen)
            .split('\\}').join(escClose)
            .split('\\,').join(escComma)
            .split('\\.').join(escPeriod);
    }

    function unescape(str) {
        return str.split(escSlash).join('\\')
            .split(escOpen).join('{')
            .split(escClose).join('}')
            .split(escComma).join(',')
            .split(escPeriod).join('.');
    }

    function parseCommaParts(str) {
        if (!str) return [''];

        var parts = [];
        var m = balancedMatch('{', '}', str);

        if (!m) return str.split(',');

        var pre = m.pre;
        var body = m.body;
        var post = m.post;
        var p = pre.split(',');

        p[p.length - 1] += '{' + body + '}';
        var postParts = parseCommaParts(post);
        if (post.length) {
            p[p.length - 1] += postParts.shift();
            p.push.apply(p, postParts);
        }

        parts.push.apply(parts, p);

        return parts;
    }

    function expandTop(str) {
        if (!str) return [];
        if (str.substr(0, 2) === '{}') str = '\\{\\}' + str.substr(2);

        return expand(escape(str), true).map(unescape);
    }

    function embrace(str) {
        return '{' + str + '}';
    }

    function isPadded(el) {
        return /^-?0\d/.test(el);
    }

    function lte(i, y) {
        return i <= y;
    }

    function gte(i, y) {
        return i >= y;
    }

    function expand(str, isTop) {
        var expansions = [];

        var m = balancedMatch('{', '}', str);
        if (!m) return [str];

        var pre = m.pre;
        var post = m.post.length ? expand(m.post, false) : [''];

        if (/\$$/.test(m.pre)) {
            for (var k = 0; k < post.length; k++) {
                var expansion = pre.substr(0, pre.length - 1) + post[k];
                expansions.push(expansion);
            }
        } else {
            var n;
            if (pre) {
                n = expand(pre, false);
            } else {
                n = [''];
            }
            for (var i = 0; i < n.length; i++) {
                for (var j = 0; j < post.length; j++) {
                    var expansion = n[i] + post[j];
                    if (!isTop || expansion)
                        expansions.push(expansion);
                }
            }
        }

        return expansions;
    }

    global.braceExpansion = expandTop;
})(typeof window !== 'undefined' ? window : this);

// minimatch (browser-compatible version)
(function(global) {
    var braceExpansion = global.braceExpansion;
    
    function Minimatch(pattern, options) {
        if (!(this instanceof Minimatch)) {
            return new Minimatch(pattern, options);
        }

        if (typeof pattern !== 'string') {
            throw new TypeError('glob pattern string required');
        }

        if (!options) options = {};
        
        this.options = options;
        this.set = [];
        this.pattern = pattern;
        this.regexp = null;
        this.negate = false;
        this.comment = false;
        this.empty = false;
        this.make();
    }

    Minimatch.prototype.debug = function() {};
    Minimatch.prototype.make = function() {
        if (this.options.nocomment !== true) {
            var commentStart = this.pattern.indexOf('#');
            if (commentStart === 0) {
                this.comment = true;
                return;
            }
        }

        if (!this.pattern) {
            this.empty = true;
            return;
        }

        this.parseNegate();
        
        var set = this.globSet = [this.pattern];
        
        // Save the original pattern for use in matching directories
        this.originalPattern = this.pattern;
        
        if (this.options.nobrace !== true) {
            set = this.braceExpand();
        }
        
        this.debug(this.pattern, set);
        
        set = this.globParts = set.map(function(s) {
            return s.split(/\/+/);
        });
        
        this.debug(this.pattern, set);
        
        set = set.map(function(s) {
            return s.map(this.parse, this);
        }, this);
        
        this.debug(this.pattern, set);
        
        set = set.filter(function(s) {
            return s.indexOf(false) === -1;
        });
        
        this.debug(this.pattern, set);
        
        this.set = set;
    };
    
    Minimatch.prototype.parseNegate = function() {
        var pattern = this.pattern;
        var negate = false;
        var options = this.options;
        var negateOffset = 0;
        
        if (options.nonegate) return;
        
        for (var i = 0; i < pattern.length && pattern.charAt(i) === '!'; i++) {
            negate = !negate;
            negateOffset++;
        }
        
        if (negateOffset) this.pattern = pattern.substr(negateOffset);
        this.negate = negate;
    };
    
    Minimatch.prototype.braceExpand = function() {
        return braceExpansion(this.pattern);
    };
    
    Minimatch.prototype.parse = function(pattern, isSub) {
        var options = this.options;
        
        if (!options.noglobstar && pattern === '**') {
            return '**';
        }
        
        if (pattern === '') return '';
        
        var re = '';
        var hasMagic = false;
        var inClass = false;
        var i;
        var c;
        var pl = pattern.length;
        var prev;
        
        for (i = 0; i < pl; i++) {
            c = pattern.charAt(i);
            if (c === '\\') {
                if (i === pl - 1) {
                    re += '\\\\';
                } else {
                    i++;
                    re += '\\' + pattern.charAt(i);
                }
                continue;
            }
            
            switch (c) {
                case '/':
                    re += '\\/';
                    break;
                    
                case '[':
                    if (!inClass) {
                        re += '[';
                        inClass = true;
                    } else {
                        re += '\\[';
                    }
                    break;
                    
                case ']':
                    if (inClass) {
                        re += ']';
                        inClass = false;
                    } else {
                        re += '\\]';
                    }
                    break;
                    
                case '*':
                    hasMagic = true;
                    if (inClass) {
                        re += '*';
                    } else {
                        re += '.*';
                    }
                    break;
                    
                case '?':
                    hasMagic = true;
                    if (inClass) {
                        re += '?';
                    } else {
                        re += '.';
                    }
                    break;
                    
                default:
                    re += c;
            }
        }
        
        if (!hasMagic) return pattern;
        return new RegExp('^' + re + '$');
    };
    
    Minimatch.prototype.match = function(file, partial) {
        if (this.comment) return false;
        if (this.empty) return file === '';
        
        if (file.indexOf('/') !== -1 && !this.options.dot) {
            var parts = file.split('/');
            for (var i = 0; i < parts.length; i++) {
                if (parts[i].charAt(0) === '.' && !this.options.dot) return false;
            }
        }

        return this.matchOne(file.split('/'), this.pattern.split('/'), partial);
    };
    
    Minimatch.prototype.matchOne = function(file, pattern, partial) {
        var options = this.options;
        
        // Handle empty patterns and filenames
        if (pattern.length === 0) {
            if (file.length === 0) return true;
            return partial;
        }
        
        if (file.length === 0) return false;
        
        var p = pattern[0];
        var f = file[0];
        
        // Handle globstars
        if (p === '**') {
            if (pattern.length === 1) return true;
            for (var i = 0; i <= file.length; i++) {
                if (this.matchOne(file.slice(i), pattern.slice(1), partial)) return true;
            }
            return false;
        }
        
        // Handle wildcards
        if (typeof p === 'string') {
            if (p === '*') {
                return this.matchOne(file.slice(1), pattern.slice(1), partial);
            }
            if (p === f) {
                return this.matchOne(file.slice(1), pattern.slice(1), partial);
            }
            return false;
        }
        
        // Handle regular expressions (converted patterns)
        if (p instanceof RegExp) {
            if (!p.test(f)) return false;
            return this.matchOne(file.slice(1), pattern.slice(1), partial);
        }
        
        return false;
    };
    
    function minimatch(p, pattern, options) {
        if (typeof pattern !== 'string') {
            throw new TypeError('glob pattern string required');
        }
        
        if (!options) options = {};
        
        // Shortcut: two identical strings must match
        if (!options.nocomment && pattern.charAt(0) === '#') {
            return false;
        }
        
        return new Minimatch(pattern, options).match(p);
    }
    
    minimatch.Minimatch = Minimatch;
    global.minimatch = minimatch;
})(typeof window !== 'undefined' ? window : this);
