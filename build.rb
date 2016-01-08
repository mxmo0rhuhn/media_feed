#!/usr/bin/env ruby

# USAGE
#
#   build.rb [input] [template] [output]
#

require 'yaml'
require 'erb'
require 'ostruct'
require 'cgi'
require 'time'

def deep_ostruct(values)
  case values
  when Hash
    OpenStruct.new.tap do |o|
      values.each do |key, value|
        o.send key.to_s + '=', deep_ostruct(value)
      end
    end
  when Array
    values.map { |v| deep_ostruct(v) }
  else values
  end
end

path = ARGV[0] || 'media.yml'
data = deep_ostruct(YAML.load(File.read(path)))
template = File.read(ARGV[1] || data.template)
now = Time.now.rfc2822

File.open(ARGV[2] || data.target, 'w') do |f|
  f.puts ERB.new(template).result
end

__END__
# Notes

def curl(url)
  output = %x[ curl -s --head --location '#{url}' ]
  {
    length: output.match(/Content-Length: (.*)\n/)[1],
    url: output.match(/Location: (.*)\n/)[1] || url
  }
end
