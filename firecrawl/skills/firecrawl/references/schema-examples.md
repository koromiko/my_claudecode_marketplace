# JSON Schema Examples for Firecrawl Extract

Patterns and examples for structured data extraction.

## Basic Patterns

### Simple Object

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "url": {"type": "string", "format": "uri"}
  },
  "required": ["title"]
}
```

### With Arrays

```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "tags": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

### Nested Objects

```json
{
  "type": "object",
  "properties": {
    "article": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "author": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"}
          }
        }
      }
    }
  }
}
```

---

## Common Use Cases

### Product Information

```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "price": {"type": "number"},
    "currency": {"type": "string"},
    "description": {"type": "string"},
    "rating": {"type": "number"},
    "reviewCount": {"type": "integer"},
    "availability": {
      "type": "string",
      "enum": ["in_stock", "out_of_stock", "pre_order"]
    },
    "features": {
      "type": "array",
      "items": {"type": "string"}
    },
    "images": {
      "type": "array",
      "items": {"type": "string", "format": "uri"}
    }
  },
  "required": ["name", "price"]
}
```

### Contact/Company Information

```json
{
  "type": "object",
  "properties": {
    "companyName": {"type": "string"},
    "address": {
      "type": "object",
      "properties": {
        "street": {"type": "string"},
        "city": {"type": "string"},
        "state": {"type": "string"},
        "postalCode": {"type": "string"},
        "country": {"type": "string"}
      }
    },
    "phone": {"type": "string"},
    "email": {"type": "string", "format": "email"},
    "website": {"type": "string", "format": "uri"},
    "socialLinks": {
      "type": "object",
      "properties": {
        "twitter": {"type": "string"},
        "linkedin": {"type": "string"},
        "facebook": {"type": "string"}
      }
    }
  }
}
```

### Article/Blog Post

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "author": {"type": "string"},
    "publishDate": {"type": "string", "format": "date"},
    "lastUpdated": {"type": "string", "format": "date"},
    "summary": {"type": "string"},
    "categories": {
      "type": "array",
      "items": {"type": "string"}
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"}
    },
    "readingTime": {"type": "integer"},
    "content": {"type": "string"}
  },
  "required": ["title", "content"]
}
```

### Job Listing

```json
{
  "type": "object",
  "properties": {
    "jobTitle": {"type": "string"},
    "company": {"type": "string"},
    "location": {"type": "string"},
    "remote": {"type": "boolean"},
    "salary": {
      "type": "object",
      "properties": {
        "min": {"type": "number"},
        "max": {"type": "number"},
        "currency": {"type": "string"},
        "period": {"type": "string", "enum": ["hourly", "annual"]}
      }
    },
    "employmentType": {
      "type": "string",
      "enum": ["full-time", "part-time", "contract", "internship"]
    },
    "requirements": {
      "type": "array",
      "items": {"type": "string"}
    },
    "benefits": {
      "type": "array",
      "items": {"type": "string"}
    },
    "applyUrl": {"type": "string", "format": "uri"}
  },
  "required": ["jobTitle", "company"]
}
```

### Event Information

```json
{
  "type": "object",
  "properties": {
    "eventName": {"type": "string"},
    "description": {"type": "string"},
    "startDate": {"type": "string", "format": "date-time"},
    "endDate": {"type": "string", "format": "date-time"},
    "location": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "address": {"type": "string"},
        "virtual": {"type": "boolean"},
        "virtualUrl": {"type": "string", "format": "uri"}
      }
    },
    "organizer": {"type": "string"},
    "ticketPrice": {"type": "number"},
    "ticketUrl": {"type": "string", "format": "uri"},
    "speakers": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "title": {"type": "string"},
          "company": {"type": "string"}
        }
      }
    }
  },
  "required": ["eventName", "startDate"]
}
```

### Documentation/API Reference

```json
{
  "type": "object",
  "properties": {
    "functionName": {"type": "string"},
    "description": {"type": "string"},
    "parameters": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string"},
          "required": {"type": "boolean"},
          "description": {"type": "string"},
          "default": {"type": "string"}
        }
      }
    },
    "returnType": {"type": "string"},
    "returnDescription": {"type": "string"},
    "examples": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "code": {"type": "string"},
          "description": {"type": "string"}
        }
      }
    }
  }
}
```

---

## Best Practices

1. **Keep schemas focused**: Extract only what you need
2. **Use required fields**: Mark essential fields as required
3. **Provide enums**: For fields with known values, use enum constraints
4. **Use appropriate types**: number vs integer, string formats (uri, email, date)
5. **Add descriptions**: Help the extraction understand field meaning
6. **Handle missing data**: Use nullable or optional fields for unreliable data

### Adding Descriptions to Fields

```json
{
  "type": "object",
  "properties": {
    "price": {
      "type": "number",
      "description": "Product price in USD without currency symbol"
    },
    "rating": {
      "type": "number",
      "description": "Average customer rating from 1-5 stars",
      "minimum": 1,
      "maximum": 5
    }
  }
}
```
