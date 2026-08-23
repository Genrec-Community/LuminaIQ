const text = 'This is a test <source 1>. And another <source 2] and [source 3] and source 4.';
const regex = /(?:&lt;|<|\[)?source\s+(\d+)(?:&gt;|>|\])?/gi;
console.log(text.replace(regex, '[$1]($1)'));
